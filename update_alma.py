# Author: Alexander Lin (alxlin@ucdavis.edu)
# Python version of update_alma.php
# Inputs: None
# Output: XML in format to be ingested by Alma
# Queries Alma to find invoices that are waiting for payment
# Queries KFS to determine if those invoices are paid

import argparse
import ConfigParser
import cx_Oracle
import json
import logging
import os
import re
import time
import xml.dom.minidom
import xml.etree.ElementTree as ET

from lib2to3.fixer_util import String
from multiprocessing.pool import ThreadPool
from urllib2 import Request, urlopen
from urllib import urlencode, quote_plus

config = ConfigParser.ConfigParser()
config.readfp(open('config.cfg'))


class erp_xml():
    """ERP formated expected XML"""
    def __init__(self):
        self.pcd = ET.Element("payment_confirmation_data",
                              {"xmlns": "http://com/exlibris/repository/acq/xmlbeans"})
        self.il = ET.SubElement(self.pcd, "invoice_list")
        self.count = 0

    def tostring(self):
        xmlstr = xml.dom.minidom.parseString(ET.tostring(self.pcd)).toprettyxml(indent="   ", encoding="UTF-8")
        return xmlstr

    def add_SubE_Text(self, parent, tag, text):
        c = ET.SubElement(parent, tag)
        c.text = text

    def add_paid_invoice(self, inv_num, alma, kfs):
        """
        Add an invoice to the list
        Reads the alma and kfs invoice return values
        """
        inv = ET.SubElement(self.il, "invoice")
        self.add_SubE_Text(inv, "invoice_number", inv_num)
        self.add_SubE_Text(inv, "unique_identifier", alma['id'])
        self.add_SubE_Text(inv, "invoice_date", re.sub(r'(\d+)-(\d+)-(\d+).*',  r'\1\2\3', alma['invoice_date']))
        self.add_SubE_Text(inv, "vendor_code", alma['vendor']['value'])
        self.add_SubE_Text(inv, "payment_status", "PAID")
        self.add_SubE_Text(inv, "payment_voucher_date", kfs['pay_date'])
        self.add_SubE_Text(inv, "payment_voucher_number", kfs['check_num'])
        amt = ET.SubElement(inv, "voucher_amount")
        self.add_SubE_Text(amt, 'currency', "USD")
        self.add_SubE_Text(amt, "sum", str(kfs['pay_amt']))
        self.count += 1


def fetch_alma_json(offset, q=None):
    if q is None:
        q = 'status~ready_to_be_paid'
    url = 'https://api-na.hosted.exlibrisgroup.com/almaws/v1/acq/invoices/'
    queryParams = '?' + urlencode({
                                quote_plus('q'): q,
                                quote_plus('limit'): '100',
                                quote_plus('offset'): offset,
                                quote_plus('format'): 'json',
                                quote_plus('apikey'): config.get("alma", "api_key")
    })
    request = Request(url + queryParams)
    request.get_method = lambda: 'GET'
    try:
        request_str = urlopen(request).read()
        return json.loads(request_str), None
    except Exception as e:
        return None, e


def list_to_dict(keyFunction, values):
    return dict((keyFunction(v), v) for v in values)


def get_waiting_invoices(q):
    """Queries Alma REST Api for Invoices waiting payment"""

    # Do the initial query to find out how many records are necessary
    request_json, error = fetch_alma_json(0, q)
    if request_json is None:
        return None, None
    trc = int(request_json['total_record_count'])
    invoices = request_json['invoice']

    # do in parallel urlopens to Alma if there are more requests needed
    if trc > 100:
        offsets = range(100, trc, 100)
        results = ThreadPool(20).imap_unordered(fetch_alma_json, offsets)
        for ret, error in results:
            if error is None:
                invoices.extend(ret['invoice'])
            else:
                logging.error("error fetching: %s" % (error))

    # Generates a list of ids along with remove any that don't have the current payment status
    nums = []
    for invoice in invoices[:]:
        nums.append(invoice['number'])
        if invoice['payment']['payment_status']['value'] != "NOT_PAID":
            logging.warn("Invoice %s payment status is not 'NOT_PAID'" % (invoice['number']))
            invoices.remove(invoice)

    # Remap list to a dictionary using id as key
    invoices = list_to_dict(lambda a: a['number'], invoices)
    return invoices, nums


def kfs_query(ids):
    """Queries Accounting KFS Database to see if the invoices are paid"""
    kfs_inv = dict()

    # If given empty set of ids
    if ids is None:
        return kfs_inv

    try:
        dsn_tns = cx_Oracle.makedsn(config.get("oracle", "server"), 1521, 'dsprod')
        con = cx_Oracle.connect(config.get("oracle", "username"),
                                config.get("oracle", "password"),
                                dsn_tns)
    except cx_Oracle.DatabaseError, exception:
        logging.error('Failed to connect to %s\n' % (config.get("oracle", "server")))
        exit(1)
    cur = con.cursor()
    q_str = ','.join("'" + item + "'" for item in ids)
    query = """
                    select * from (
                        select DV.fdoc_nbr                              AS doc_num
                            , PD.dv_payee_id_nbr                        AS vendor_id
                            , PD.dv_payee_prsn_nm                       AS vendor_name
                            , NVL(PPD.inv_nbr, 'MISSING INV#')          AS vendor_invoice_num
                            , NVL(DV.dv_chk_nbr, ' ')                   AS check_num
                            , DV.dv_chk_tot_amt                         AS payment_total_amt
                            , to_char(DV.dv_pd_dt, 'YYYYMMDD')          AS payment_entered_date
                            , DT.doc_typ_nm                             AS doc_type
                          from finance.fp_dv_doc_t DV
                            join finance.fp_dv_payee_dtl_t PD
                              on PD.fdoc_nbr = DV.fdoc_nbr
                            join finance.rice_krew_doc_hdr_ext_t DHX
                              on DHX.doc_hdr_id = DV.fdoc_nbr
                            join finance.rice_krew_doc_hdr_t DH
                              on DH.doc_hdr_id = DV.fdoc_nbr
                            join finance.rice_krew_doc_typ_t DT
                              on DT.doc_typ_id = DH.doc_typ_id
                            join finance.pdp_pmt_dtl_t PPD
                              on ppd.cust_pmt_doc_nbr = DV.fdoc_nbr
                          where DHX.val in
                              ( 'ULBK'
                              , 'BKDE'
                              , 'BKDG'
                              , 'BKFE'
                              , 'BKRE'
                              )
                        UNION
                        select CM.fdoc_nbr                         AS doc_num
                            , CM.vndr_cust_nbr                     AS vendor_id
                            , CM.vndr_nm                           AS vendor_name
                            , CM.crdt_memo_nbr                     AS vendor_invoice_num
                            , nvl(CM.pmt_disb_nbr, ' ')            AS check_num
                            , CM.crdt_memo_amt                     AS payment_total_amt
                            , to_char(CM.ap_aprvl_dt, 'YYYYMMDD')  AS payment_entered_date
                            , DT.doc_typ_nm                        AS doc_type
                          from finance.ap_crdt_memo_t CM
                            join finance.rice_krew_doc_hdr_t DH
                              on DH.doc_hdr_id = CM.fdoc_nbr
                            join finance.rice_krew_doc_typ_t DT
                              on DT.doc_typ_id = DH.doc_typ_id
                          where cm_feed_cd = 'LG'
                        )
                      where vendor_invoice_num IN (%s)
                      order by doc_num
    """ % (q_str)

    if cur.execute(query):
        for doc_num, vendor_id, vendor_name, num, check_num, pay_amt, pay_date, doc_type in cur:
            if num in kfs_inv:
                logging.warn("Multiple invoice numbers detected: %s: Skipping invoice" % num)
                kfs_inv.pop(num)
            else:
                kfs_inv[num] = {'doc_num': doc_num,
                                'vendor_id': vendor_id,
                                'vendor_name': vendor_name,
                                'check_num': check_num,
                                'pay_amt': pay_amt,
                                'pay_date': pay_date}
    else:
        logging.error("KFS Query Failed")
    con.close()

    return kfs_inv

if __name__ == "__main__":
    # Build XML
    erp = erp_xml()

    # Constants
    mytime = int(time.time())
    cwd = os.getcwd()
    log_dir = os.path.join(cwd, "logs")
    latest_log = os.path.join(log_dir, "update_alma.latest.log")

    # Read in Command line Arguments
    parser = argparse.ArgumentParser(description='KFS to Alma Invoice Updater')
    parser.add_argument('-o', '--output-file',
                        default="update_alma_%d.input.xml" % mytime,
                        help='output file name (default: update_alma_(time).input.xml)')
    parser.add_argument('-q', '--query',
                        default=None,
                        help='custom query for Alma RESTful API'
                        )
    parser.add_argument('-l', '--log-file',
                        default="update_alma.%d.log" % mytime,
                        help='logfile name (default: update_alma.<time>.log)')
    parser.add_argument('--log-level',
                        default='INFO',
                        help='log level of written log (default: INFO) Possible [DEBUG, INFO, WARNING, ERROR, CRITICAL]')
    args = parser.parse_args()

    # Create and setup logging
    if not os.path.isdir(log_dir):
        os.mkdir(log_dir)
    log_file_path = os.path.join(log_dir, args.log_file)

    numeric_level = getattr(logging, args.log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % args.log_level)
    logging.basicConfig(filename=log_file_path,
                        level=numeric_level)

    # Get Alma invoices
    invoices, nums = get_waiting_invoices(args.query)

    # Query KFS Oracle DB
    for inv_num, kfs_inv in sorted(kfs_query(nums).iteritems()):
        if kfs_inv['pay_amt'] != invoices[inv_num]['total_amount']:
            logging.warn("Invoice(%s) payment record doesn't match KFS (%s != %s)" % (inv_num, kfs_inv['pay_amt'], invoices[inv_num]['total_amount']))
        erp.add_paid_invoice(inv_num, invoices[inv_num], kfs_inv)

    if erp.count > 0:
        with open(args.output_file, 'w') as xml_file:
            xml_file.write(erp.tostring())
    else:
        logging.info("Nothing to update from ERP!")

    # set current log as latest log
    if os.path.lexists(latest_log):
        os.unlink(latest_log)
    os.symlink(log_file_path, latest_log)

#!/usr/bin/env python2.7

"""
Author: Alexander Lin (alxlin@ucdavis.edu)
Python version of update_alma.php
Inputs: None
Output: XML in format to be ingested by Alma
Queries Alma to find invoices that are waiting for payment
Queries KFS to determine if those invoices are paid
"""

import argparse
import ConfigParser
import json
import logging
import os
import re
import shutil
import time
import xml.dom.minidom
import xml.etree.ElementTree as ET

from multiprocessing.pool import ThreadPool
from urllib2 import Request, urlopen, HTTPError
from urllib import urlencode, quote_plus

import cx_Oracle

# Read config from config.ini
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, 'config.ini')
CONFIG = ConfigParser.ConfigParser()
CONFIG.readfp(open(CONFIG_PATH))

def add_subele_text(parent, tag, text):
    """
    Add varable as tag and text to element tree
    """
    child = ET.SubElement(parent, tag)
    child.text = text


class ErpXml(object):
    """ERP formated expected XML"""
    def __init__(self):
        self.pcd = ET.Element(
            "payment_confirmation_data",
            {"xmlns": "http://com/exlibris/repository/acq/xmlbeans"}
        )
        self.inv_list = ET.SubElement(self.pcd, "invoice_list")
        self.count = 0

    def to_string(self):
        """
        Print the ERP to XML in string format
        """
        xmldom = xml.dom.minidom.parseString(ET.tostring(self.pcd))
        xmlstr = xmldom.toprettyxml(indent="   ", encoding="UTF-8")
        return xmlstr

    def add_paid_invoice(self, num, alma, kfs):
        """
        Add an invoice to the list
        Reads the alma and kfs invoice return values
        num = invoice number
        alma = data sent by alma
        kfs = hash sent by kfs
        """
        inv = ET.SubElement(self.inv_list, "invoice")
        add_subele_text(inv, "invoice_number", num)
        add_subele_text(inv, "unique_identifier", alma['id'])
        add_subele_text(
            inv,
            "invoice_date",
            re.sub(r'(\d+)-(\d+)-(\d+).*', r'\1\2\3', alma['invoice_date'])
        )
        add_subele_text(inv, "vendor_code", alma['vendor']['value'])
        add_subele_text(inv, "payment_status", "PAID")
        add_subele_text(inv, "payment_voucher_date", kfs['pay_date'])
        add_subele_text(inv, "payment_voucher_number", kfs['check_num'])
        amt = ET.SubElement(inv, "voucher_amount")
        add_subele_text(amt, 'currency', "USD")
        add_subele_text(amt, "sum", str(kfs['pay_amt']))
        self.count += 1


def fetch_alma_json(offset, query=None):
    """
    Queries alma using REST API
    query - string optional used if you want to modify the query
    """
    if query is None:
        query = 'status~ready_to_be_paid'
    url = 'https://api-na.hosted.exlibrisgroup.com/almaws/v1/acq/invoices/'
    query_params = '?' + urlencode({
        quote_plus('q'): query,
        quote_plus('limit'): '100',
        quote_plus('offset'): offset,
        quote_plus('format'): 'json',
        quote_plus('apikey'): CONFIG.get("alma", "api_key")
    })
    request = Request(url + query_params)
    request.get_method = lambda: 'GET'
    try:
        request_str = urlopen(request).read()
        return json.loads(request_str), None
    except HTTPError as err:
        logging.error('HTTPError = ' + str(err.code))


def list_to_dict(key_function, values):
    """
    turns list to dictionary using function
    """
    return dict((key_function(v), v) for v in values)


def get_waiting_invoices(query):
    """Queries Alma REST Api for Invoices waiting payment"""

    logging.info("Getting Waiting Invoices")
    # Do the initial query to find out how many records are necessary
    request_json, error = fetch_alma_json(0, query)
    if request_json is None:
        return None, None
    trc = int(request_json['total_record_count'])
    invs = request_json['invoice']

    # do in parallel urlopens to Alma if there are more requests needed
    if trc > 100:
        offsets = range(100, trc, 100)
        results = ThreadPool(20).imap_unordered(fetch_alma_json, offsets)
        for ret, error in results:
            if error is None:
                invs.extend(ret['invoice'])
            else:
                logging.error("error fetching: %s", error)

    # Generates a list of ids along
    # with remove any that don't have the current payment status
    inv_nums = []
    for invoice in invs[:]:
        inv_nums.append(invoice['number'])
        if invoice['payment']['payment_status']['value'] != "NOT_PAID":
            logging.warn(
                "Invoice %s payment status is not 'NOT_PAID'",
                invoice['number']
            )
            invs.remove(invoice)

    # Remap list to a dictionary using id as key
    invs = list_to_dict(lambda a: a['number'], invs)
    return invs, inv_nums


def kfs_query(ids):
    """Queries Accounting KFS Database to see if the invoices are paid"""
    kfs_invs = dict()
    logging.info("Running KFS Query")
    # If given empty set of ids
    if ids is None:
        return kfs_invs

    try:
        con = cx_Oracle.connect(CONFIG.get("oracle", "username"),
                                CONFIG.get("oracle", "password"),
                                cx_Oracle.makedsn(
                                    CONFIG.get("oracle", "server"),
                                    1521,
                                    'dsprod'
                                    )
                               )
    except cx_Oracle.DatabaseError:
        logging.error(
            'Failed to connect to %s\n',
            CONFIG.get("oracle", "server")
        )
        exit(1)
    cur = con.cursor()
    q_str = ','.join("'" + item + "'" for item in ids)
    query = """
        select * from (
            select DV.fdoc_nbr AS doc_num
                , PD.dv_payee_id_nbr               AS vendor_id
                , PD.dv_payee_prsn_nm              AS vendor_name
                , NVL(PPD.inv_nbr, 'MISSING INV#') AS vendor_invoice_num
                , NVL(DV.dv_chk_nbr, ' ')          AS check_num
                , DV.dv_chk_tot_amt                AS payment_total_amt
                , to_char(DV.dv_pd_dt, 'YYYYMMDD') AS payment_entered_date
                , DT.doc_typ_nm                    AS doc_type
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
        for res in cur:
            (doc_num,
             vendor_id,
             vendor_name,
             num,
             check_num,
             pay_amt,
             pay_date,
             doc_type) = res
            if num in kfs_invs:
                logging.warn(
                    "Multiple invoice numbers detected: "
                    "%s: Skipping invoice",
                    num
                )
                kfs_invs.pop(num)
            else:
                kfs_invs[num] = {'doc_num': doc_num,
                                 'vendor_id': vendor_id,
                                 'vendor_name': vendor_name,
                                 'check_num': check_num,
                                 'pay_amt': pay_amt,
                                 'pay_date': pay_date,
                                 'doc_type' : doc_type}
    else:
        logging.error("KFS Query Failed")
    con.close()

    return kfs_invs

# pylint: disable=C0103
if __name__ == '__main__':
    # Build XML
    erp = ErpXml()

    # Constants
    mytime = int(time.time())
    cwd = os.getcwd()
    archive_dir = os.path.join(cwd, "archive")

    # Read in Command line Arguments
    parser = argparse.ArgumentParser(description='KFS to Alma Invoice Updater')
    parser.add_argument(
        '-o', '--output-file',
        default="update_alma_%d.input.xml" % mytime,
        help='output file name (default: update_alma_(time).input.xml)'
    )
    parser.add_argument(
        '--output-dir',
        default=cwd,
        help="Directory for output file (default: %s)" % cwd
    )
    parser.add_argument(
        '-q', '--query',
        default=None,
        help='custom query for Alma RESTful API'
    )
    parser.add_argument(
        '-l', '--log-file',
        default="update_alma.%d.log" % mytime,
        help='logfile name (default: update_alma.<time>.log)'
    )
    parser.add_argument(
        '--log-dir',
        default=os.path.join(cwd, "logs"),
        help='log directory (default: <cwd>/logs)'
    )
    parser.add_argument(
        '--log-level',
        default='INFO',
        help='log level of written log (default: INFO) '
        'Possible [DEBUG, INFO, WARNING, ERROR, CRITICAL]'
    )
    parser.add_argument(
        '-t', '--tolerance',
        default=1,
        help='percentage of tolerance allowed in paid amount from KFS to Alma'
    )
    args = parser.parse_args()

    tolerance = float(args.tolerance)/100

    # Create and setup logging
    latest_log = os.path.join(args.log_dir, "update_alma.latest.log")
    if not os.path.isdir(args.log_dir):
        os.mkdir(args.log_dir)
    log_file_path = os.path.join(args.log_dir, args.log_file)

    numeric_level = getattr(logging, args.log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % args.log_level)
    logging.basicConfig(
        filename=log_file_path,
        level=numeric_level,
        format="[%(threadName)-12.12s] [%(levelname)-5.5s] %(message)s"
    )
    logger = logging.getLogger()
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(numeric_level)

    # Setup archive
    if not os.path.isdir(archive_dir):
        os.mkdir(archive_dir)
    input_archive = os.path.join(archive_dir, "alma_input")
    if not os.path.isdir(input_archive):
        os.mkdir(input_archive)

    # Get Alma invoices
    invoices, nums = get_waiting_invoices(args.query)

    # Query KFS Oracle DB
    for inv_num, kfs_inv in sorted(kfs_query(nums).iteritems()):
        diff = abs(kfs_inv['pay_amt'] - invoices[inv_num]['total_amount'])
        if diff > float(invoices[inv_num]['total_amount']) * tolerance:
            logging.error(
                "Invoice(%s) payment record doesn't match Alma"
                " Outside tolerance of %d"
                " (%s != %s)",
                inv_num,
                args.tolerance,
                kfs_inv['pay_amt'],
                invoices[inv_num]['total_amount']
            )
        erp.add_paid_invoice(inv_num, invoices[inv_num], kfs_inv)

    if erp.count > 0:
        output_file_path = os.path.join(args.output_dir, args.output_file)
        with open(output_file_path, 'w') as xml_file:
            xml_file.write(erp.to_string())
        shutil.copy(output_file_path, input_archive)
        logging.info("Output XML created: %s", output_file_path)
    else:
        logging.info("Nothing to update from ERP!")

    # set current log as latest log
    if os.path.lexists(latest_log):
        os.unlink(latest_log)
    os.symlink(log_file_path, latest_log)
    logging.info("Done")

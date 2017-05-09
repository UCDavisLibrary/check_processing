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
import csv
import json
import logging
import os
import re
import shutil
import sys
import traceback
import time
import xml.dom.minidom
import xml.etree.ElementTree as ET

from datetime import datetime
from multiprocessing import Pool
from urllib import quote_plus, quote

import cx_Oracle
import requests

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
        self.invs = []
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
        logging.debug("kfs:[%s]", ','.join(map(str, kfs.values())))
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
        pay_date = ""
        if kfs['pay_date']:
            pay_date = datetime.strptime(kfs['pay_date'], "%Y%m%d")
            pay_date = pay_date.strftime("%m/%d/%Y")
        self.invs.append([kfs['doc_num'],
                          kfs['vendor_id'],
                          kfs['vendor_name'],
                          num,
                          kfs['check_num'],
                          "%.2f" % float(kfs['pay_amt']),
                          pay_date])
        self.count += 1

def fetch_alma_json(offset, query=None):
    """
    Queries alma using REST API
    query - string optional used if you want to modify the query
    """
    if query is None:
        query = 'status~ready_to_be_paid'
    url = 'https://api-na.hosted.exlibrisgroup.com/almaws/v1/acq/invoices/'
    query_params = {
        quote_plus('q'): query,
        quote_plus('limit'): '100',
        quote_plus('offset'): offset,
        quote_plus('format'): 'json',
        quote_plus('apikey'): CONFIG.get("alma", "api_key")
    }
    req = requests.get(url, params=query_params)
    return json.loads(req.text), None

def fetch_vendor_code(code):
    """Uses Alma Web Api to get vendor id"""
    url = "https://api-na.hosted.exlibrisgroup.com/almaws/v1/acq/vendors/%s" % quote(code)
    query_params = {
        quote_plus('format') : 'json',
        quote_plus('apikey') : CONFIG.get("alma", "api_key")
    }
    try:
        session = requests.Session()
        req = session.get(url, params=query_params)
        data = json.loads(req.text)
        first, second = re.split(r"\D+", data['additional_code'], 2)
        return code, first.lstrip("0") + '-' + second[0]
    except:
        logging.warn("Trying to get json of vendor code: " + code)
        logging.warn("Error: %s", sys.exc_info()[0])
        traceback.print_exc()
        return code, ""

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
        pool = Pool(processes=20)
        results = pool.imap_unordered(fetch_alma_json, offsets)
        pool.close()
        pool.join()
        for ret, error in results:
            if error is None:
                invs.extend(ret['invoice'])
            else:
                logging.error("error fetching: %s", error)

    # Generates a list of ids along
    # with remove any that don't have the current payment status
    inv_nums = []
    vendor_codes = []
    for invoice in invs[:]:
        invoice['number'] = invoice['number'].strip()
        if invoice['payment']['payment_status']['value'] != "NOT_PAID":
            logging.warn(
                "Invoice %s payment status is not 'NOT_PAID'",
                invoice['number']
            )
        inv_nums.append(invoice['number'])
        if  invoice['vendor']['value'] not in vendor_codes:
            vendor_codes.append(invoice['vendor']['value'])

    # Remap list to a dictionary using id as key
    invs = list_to_dict(lambda a: a['number'], invs)

    # Get Vendors and their Vendor Ids
    vendors = dict()
    inv_vend_ids = dict()
    pool = Pool(processes=20)
    results = pool.imap_unordered(fetch_vendor_code, vendor_codes)
    pool.close()
    pool.join()
    for code, vend_id in results:
        if error is None:
            vendors[code] = vend_id
        else:
            logging.error("error fetching: %s", error)
    for num in inv_nums:
        inv_vend_ids[num] = vendors[invs[num]['vendor']['value']]
    return invs, inv_nums, inv_vend_ids

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
    logging.debug("Querying invoices: %s", q_str)

    if cur.execute(query):
        return cur
    else:
        logging.error("KFS Query Failed")
    con.close()

    return kfs_invs

def process_query(cur, vendors, interactive):
    """
    Takes connection cursor and generates dictionary of query
    Also matches them by vendor id
    """
    kfs_invs = dict()
    out = dict()
    for res in cur:
        keys = ['doc_num', 'vendor_id', 'vendor_name', 'num',
                'check_num', 'pay_amt', 'pay_date', 'doc_type']
        kfs_d = dict(zip(keys, res))
        num = kfs_d['num']
        if vendors and num in vendors and vendors[num] != kfs_d['vendor_id'] and vendors[num]:
            logging.debug("Invoice(%s) didn't have right vendor_id skipped"
                          " Expected %s got: %s", num, vendors[num], kfs_d['vendor_id'])
            continue
        if num in kfs_invs:
            logging.info("Multiple invoice numbers detected: ")
            # check if the duplicate is the exact same
            dup = False
            for kin in kfs_invs[num]:
                dup = dup or equal_dicts(kin, kfs_d, ['doc_num'])
            if not dup:
                kfs_invs[num].append(kfs_d)
        else:
            kfs_invs[num] = [kfs_d]

    for key, kinv in kfs_invs.iteritems():
        if len(kinv) == 1:
            out[key] = kinv[0]
        elif interactive:
            logging.info("Invoice(%s) has multiple entries in KFS", key)
            logging.info("[0] None of the above")
            count = 1
            for opts in kinv:
                logging.info("[%d] %s", count, "|".join(str(v) for v in opts.values()))
                count += 1
            choice = 0
            while True:
                inp = raw_input("Your choice:")
                if inp.isdigit() and int(inp) <= len(kinv):
                    choice = int(inp)
                    break
                else:
                    logging.warn("Value not permitted")
            if choice == 0:
                logging.info("Skipping invoice(%s)", key)
            else:
                logging.info("Using choice %d", choice)
                out[key] = kinv[choice - 1]
        else:
            logging.warn("Multiple invoices with different data: Skipping invoice(%s)",
                         key)
    return out

def equal_dicts(dic1, dic2, ignore_keys):
    """compares two diciontaries ignoring specific keys"""
    d1_filtered = dict((k, v) for k, v in dic1.iteritems() if k not in ignore_keys)
    d2_filtered = dict((k, v) for k, v in dic2.iteritems() if k not in ignore_keys)
    return d1_filtered == d2_filtered

# pylint: disable=C0103
if __name__ == '__main__':
    # Build XML
    erp = ErpXml()

    # Constants
    mytime = int(time.time())
    cwd = os.getcwd()

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
        '--archive-dir',
        default=os.path.join(cwd, "archive"),
        help='archive directory (default: <cwd>/archive)'
    )
    parser.add_argument(
        '-t', '--tolerance',
        default=1,
        help='percentage of tolerance allowed in paid amount from KFS to Alma'
    )
    parser.add_argument(
        '--report-dir',
        default=os.path.join(cwd, "reports"),
        help='report directory (default: <cwd>/reports'
    )
    parser.add_argument(
        '--report-file',
        default="check_information_report.%d.csv" % mytime,
        help='report file name (default: check_information_report.<time>.csv)'
    )
    parser.add_argument(
        '-i', '--interactive',
        action='store_true',
        default=False
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
        format="[%(levelname)-5.5s] %(message)s"
    )
    logger = logging.getLogger()
    consoleHandler = logging.StreamHandler()
    stream_format = logging.Formatter("[%(levelname)-5.5s] %(message)s")
    consoleHandler.setFormatter(stream_format)
    logger.addHandler(consoleHandler)
    logger.setLevel(numeric_level)

    # Setup archive
    if not os.path.isdir(args.archive_dir):
        os.mkdir(args.archive_dir)
    input_archive = os.path.join(args.archive_dir, "alma_input")
    if not os.path.isdir(input_archive):
        os.mkdir(input_archive)

    # Get Alma invoices
    invoices, nums, inv_vendids = get_waiting_invoices(args.query)

    # Query KFS Oracle DB
    cursor = kfs_query(nums)
    kfs_hash = process_query(cursor, inv_vendids, args.interactive)
    for inv_num, kfs_inv in sorted(kfs_hash.iteritems()):
        if inv_num not in invoices:
            logging.warn("%s not found in Alma but is in KFS: Skipping", inv_num)
            continue
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
        # Generate report
        if not os.path.isdir(args.report_dir):
            os.mkdir(args.report_dir)
        report_file = os.path.join(args.report_dir, args.report_file)
        logging.info("Creating Check Information File: %s", report_file)
        with open(report_file, 'wb') as report_file:
            w = csv.writer(report_file)
            w.writerow(('Doc #',
                        'Vender #',
                        'Vender Name',
                        'Invoice #',
                        'Check #',
                        'Amount',
                        'Date'))
            for r in erp.invs:
                w.writerow(r)

    else:
        logging.info("Nothing to update from ERP!")

    # set current log as latest log
    if os.path.lexists(latest_log):
        os.unlink(latest_log)
    os.symlink(log_file_path, latest_log)
    logging.info("Log file: %s", log_file_path)
    logging.info("Done")

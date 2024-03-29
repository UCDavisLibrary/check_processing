#!/usr/bin/env python2.7

"""
Author: Alexander Lin (alxlin@ucdavis.edu)
Python version of xml_to_apfeed.php
Inputs: XMLs
Output: Apfeeds
Reads exported XML generated by Alma for upload to ERP finanical system
Creates an apfeed file, which is a flat text file
"""

import argparse
import ConfigParser
import csv
import datetime
import logging
import os
import shutil
import re
import sys
import time
import xml.etree.ElementTree as ET

# Read config from config.ini
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, 'config.ini')
CONFIG = ConfigParser.ConfigParser()
CONFIG.readfp(open(CONFIG_PATH))
UTAX = float(CONFIG.get('apfeed', 'tax_perc'))

NSP = {'exl': 'http://com/exlibris/repository/acq/invoice/xmlbeans'}


def strstr(haystack, needle):
    """
    Python version of php str str
    """
    pos = haystack.upper().find(needle.upper())
    if pos < 0:
        return haystack
    else:
        return haystack[:pos] + "}"


class Apfeed(object):
    """Class to model what apfeed should be generated"""

    def __init__(self):
        """Initialization"""
        self.now = datetime.datetime.now()
        self.count = 0
        self.invoices = []
        self.org_doc_nbr = int(CONFIG.get("apfeed", "org_doc_nbr"))
        self.emp_ind = CONFIG.get('apfeed', 'emp_ind')
        self.errors = 0
        self.eids = dict()
        self.invs = dict()

        # will be set later
        self.goods_received_dt = " " * 8
        self.attachment_req_ind = 'N'
        self.pmt_tax_cd_inv = '0'
        self.vend_assign_inv_nbr = None
        self.vend_nbr = None
        self.addr_select_vend_nbr = None
        self.vend_assign_inv_date = None
        self.inv_header = ""

        # Constants
        self.pmt_remit_nm = " " * 40
        self.pmt_remit_line_1_addr = " " * 40
        self.pmt_remit_line_2_addr = " " * 40
        self.pmt_remit_line_3_addr = " " * 40
        self.pmt_remit_city_nm = " " * 40
        self.pmt_remit_st_cd = " " * 2
        self.pmt_remit_zip_cd = " " * 11
        self.pmt_remit_cntry_cd = " " * 2
        self.vend_st_res_ind = " "
        self.inv_received_dt = " " * 8
        self.org_shp_zip_cd = CONFIG.get("apfeed", "org_shp_zip_cd")
        self.org_shp_state_cd = CONFIG.get("apfeed", "org_shp_state_cd")
        self.pmt_grp_cd = CONFIG.get("apfeed", "pmt_grp_cd")
        self.inv_fob_cd = " " * 2
        self.disc_term_cd = " " * 2
        self.scheduled_pmt_dt = self.now.strftime("%Y%m%d")
        self.pmt_non_check_ind = CONFIG.get("apfeed", "pmt_non_check_ind")
        self.fin_coa_cd = CONFIG.get("apfeed", "fin_coa_cd")
        self.sub_acct_nbr = " " * 5
        self.fin_object_cd = CONFIG.get('apfeed', 'fin_object_cd')
        self.fin_sub_obj_cd = " " * 3
        self.project_cd = " " * 10
        self.apply_disc_ind = CONFIG.get('apfeed', 'apply_disc_ind')
        self.eft_override_ind = CONFIG.get('apfeed', 'eft_override_ind')
        self.ap_pmt_purpose_desc = " " * 120

    def report_line(self, eid, amt, utax):
        """Calculates total charges by external ids (eids) and invoice id.

        For reporting. Stores data in dictionary.

        Args:
            eid (str): External id number of account. e.g. MAINBKS, HSBOOKS
            amt: Base amount eid will be charged. Should match line item price.
            utax: Tax code of line item.

        """
        amt = float(amt) / 100
        if eid not in self.eids:
            self.eids[eid] = {'amt': 0, 'tax': 0}
        self.eids[eid]['amt'] += amt
        inv_num = self.vend_assign_inv_nbr
        if inv_num not in self.invs:
            self.invs[inv_num] = {'total': 0, 'tax': 0}

        self.invs[inv_num]['total'] += amt

        # calculate tax based on rate in config file.
        if utax != '0':
            tax = amt * UTAX / 100
            self.eids[eid]['tax'] += tax
            self.invs[inv_num]['tax'] += tax

    def note_list(self, inv):
        """Handles the notes field flags

        ATTACH - Attachment
        UTAX - use tax both for inv and inv_line
        ATAX - Both
        Called from add_inv.

        Args:
            inv (ElementTree): A single parsed invoice ElementTree.

        """
        note_list = inv.find("exl:noteList", NSP)
        if note_list is None:
            create_dt = inv.find("exl:invoice_ownered_entity/exl:creationDate", NSP)
            if create_dt is not None:
                self.goods_received_dt = create_dt.text
        else:
            self.goods_received_dt = note_list.find(
                "exl:note/exl:owneredEntity/exl:creationDate", NSP
            ).text
            content = note_list.find("exl:note/exl:content", NSP).text
            if content == "ATTACH" or content == "ATAX":
                self.attachment_req_ind = 'Y'
            if content == "UTAX" or content == "ATAX":
                self.pmt_tax_cd_inv = "C"

    def add_inv(self, inv):
        """Formats each invoice line item as a fixed-width string (apfeed).

        Apfeed file format as follows:
        'GENERALLIBRARY AAAAAAAAAAAAAABBBBBBBCDDDDDDDDDDDEEEEEEEEEEEEEE'
        'FFFFFFFFGGGGGGGGGGGGGG                                          '
        '               HHHHHHHHHIIIIIIIIII JJK     LLLLLLLLMNOOOOO3 '
        'QQQQQQQ     RRRR          SSSSSSSSTUUUUUUUUUUUUVW             '
        '                           '
        Values  | Position   | Description
        A       | 15  - 29   | time now in %Y%m%d%H%M%S
        B       | 29  - 36   | ORG_DOC_NBR
        C       | 36  - 37   | EMP_IND
        D       | 37  - 47   | VEND_CODE
        E       | 47  - 62   | VEND_ASSIGN_INV_NBR
        F       | 62  - 70   | VEND_ASSIGN_INV_DATE
        G       | 70  - 84   | ADDR_SELECT_VEND_NBR
        H       | 308 - 316  | GOODS_RECEIVED_DT
        I       | 316 - 327  | ORG_SHP_ZIP_CD
        J       | 327 - 329  | ORG_SHP_STATE_CD
        K       | 329 - 330  | PMT_GRP_CD
        L       | 335 - 343  | SCHEDULED_PMT_DT
        M       | 343 - 344  | PMT_NON_CHECK_IND
        N       | 344 - 345  | ATTACHMENT_REQ_IND
        O       | 345 - 350  | PMT_LINE_NBR
        P       | 350 - 351  | FIN_COA_CD
        Q       | 352 - 359  | ACCOUNT_NBR
        R       | 364 - 368  | FIN_OBJECT_CD
        S       | 381 - 389  | ORG_REFERENCE_ID
        T       | 389 - 390  | PMT_TAX_CD
        U       | 390 - 402  | PMT_AMT
        V       | 402 - 403  | APPLY_DISC_IND
        W       | 403 - 404  | EFT_OVERRIDE_IND

        Constructs inv_header string, which contains data specific to invoice.
        Then line method is called, which appends data specific to a line.

        Args:
            inv (ElementTree): A single parsed invoice ElementTree.
                Often contains multiple line items.
        """

        # defaults per line
        self.attachment_req_ind = 'N'
        self.pmt_tax_cd_inv = '0'

        self.org_doc_nbr += 1
        # Foreach of the invoice lines
        self.vend_nbr = inv.find("exl:vendor_additional_code", NSP).text
        self.vend_assign_inv_nbr = inv.find("exl:invoice_number", NSP).text
        logging.debug("Invoice Number: %s", self.vend_assign_inv_nbr)
        self.vend_assign_inv_date = datetime.datetime.strptime(
            inv.find("exl:invoice_date", NSP).text,
            "%m/%d/%Y"
        )
        self.addr_select_vend_nbr = inv.find(
            "exl:vendor_additional_code", NSP
        ).text.replace(" ", "")

        vat_amt = float(
            inv.find("exl:vat_info/exl:vat_amount", NSP).text
        )
        if vat_amt > 0:
            self.pmt_tax_cd_inv = 'A'

        self.note_list(inv)

        if self.validate() > 0:
            return

        istr = "GENERALLIBRARY "
        istr += self.now.strftime("%Y%m%d%H%M%S")
        istr += "{:07d}".format(self.org_doc_nbr)
        istr += self.emp_ind
        istr += self.vend_nbr[0:10]
        istr += "{:15}".format(self.vend_assign_inv_nbr[0:15])
        istr += self.vend_assign_inv_date.strftime("%Y%m%d")
        istr += self.addr_select_vend_nbr[0:14]
        istr += self.pmt_remit_nm
        istr += self.pmt_remit_line_1_addr
        istr += self.pmt_remit_line_2_addr
        istr += self.pmt_remit_line_3_addr
        istr += self.pmt_remit_city_nm
        istr += self.pmt_remit_st_cd
        istr += self.pmt_remit_zip_cd
        istr += self.pmt_remit_cntry_cd
        istr += self.vend_st_res_ind
        istr += self.inv_received_dt
        istr += self.goods_received_dt[0:8]
        istr += self.org_shp_zip_cd[0:11]
        istr += " "
        istr += self.org_shp_state_cd[0:2]
        istr += self.pmt_grp_cd
        istr += self.inv_fob_cd
        istr += self.disc_term_cd
        istr += " "
        istr += self.scheduled_pmt_dt
        istr += self.pmt_non_check_ind
        istr += self.attachment_req_ind
        self.inv_header = istr

        # Per line creation
        inv_list = inv.findall("./exl:invoice_line_list/exl:invoice_line", NSP)
        for inv_line in inv_list:
            self.line(inv_line)

    def line(self, inv_line, fund_index=0):
        """Adds line-specific data to invoice fixed-width string.

        Appends formatted string to invoices instance attribute.

        Args:
            inv_line (ElementTree): A single parsed line item from an invoice

        """
        pmt_line_nbr = int(inv_line.find("exl:line_number", NSP).text)
        logging.debug("- Line Number: %s", pmt_line_nbr)
        ext_id = inv_line.findall(
            "exl:fund_info_list/exl:fund_info/exl:external_id",
            NSP
        )

        # check if an invoice line is split across multiple funds
        if len(ext_id) == 1:
            ext_id = ext_id[0]
        elif len(ext_id) > 1:
            logging.debug("Line has multiple funds")
            next_fund = fund_index + 1
            if next_fund < len(ext_id):
                self.line(inv_line, next_fund)
            ext_id = ext_id[fund_index]
        else:
            ext_id = None

        po_line_nbr = inv_line.find(
            "exl:po_line_info/exl:po_line_number",
            NSP
        )
        if po_line_nbr is None:
            org_reference_id = " " * 8
        else:
            org_reference_id = strstr(po_line_nbr.text, '-')

        amt_sum = inv_line.findall(
            "exl:fund_info_list/exl:fund_info/exl:amount/exl:sum",
            NSP
        )
        if len(amt_sum) > 0:
            amt_sum = amt_sum[fund_index]
        else:
            amt_sum = None

        # Probably a empty line
        if ext_id is None and amt_sum is None:
            logging.debug(
                "Invoice(%s) Line number: %d is empty - Skipping",
                self.vend_assign_inv_nbr,
                pmt_line_nbr
            )
            return

        pmt_amt = int(float(amt_sum.text) * 100)
        account_nbr = ext_id.text

        note = inv_line.find("exl:note", NSP)
        pmt_tax_cd = self.pmt_tax_cd_inv
        if note is not None:
            if self.pmt_tax_cd_inv == 'C' and note.text and re.match(r"\bNUTAX\b", note.text):
                pmt_tax_cd = '0'
            elif note.text and re.match(r"\bUTAX\b", note.text):
                pmt_tax_cd = 'C'

        # report
        self.report_line(account_nbr, pmt_amt, pmt_tax_cd)

        if self.validate_line(pmt_tax_cd) > 0:
            return

        istr = self.inv_header
        istr += "{:05d}".format(pmt_line_nbr)
        istr += self.fin_coa_cd
        istr += " "
        istr += account_nbr[0:7]
        istr += self.sub_acct_nbr
        istr += self.fin_object_cd
        istr += self.fin_sub_obj_cd
        istr += self.project_cd
        istr += "{:8}".format(org_reference_id[0:8])
        istr += pmt_tax_cd
        istr += "{:012d}".format(pmt_amt)
        istr += self.apply_disc_ind
        istr += self.eft_override_ind
        istr += self.ap_pmt_purpose_desc

        self.invoices.append(istr)
        self.count += 1

    def validate(self):
        """
        Runs validations on an invoice ElementTree
        before its lines are staged for output.
        Will update the number of errors.
        For non-line item invoice data.
        """

        # Cannot have invoice date in the future
        if self.vend_assign_inv_date.date() > self.now.date():
            logging.error("Skipping(%s) Invoice date(%s) is in the future",
                          self.vend_assign_inv_nbr,
                          self.vend_assign_inv_date)
            self.errors += 1

        if len(self.addr_select_vend_nbr) < 14:
            logging.error("Skipping(%s) addr_select_vend_nbr(%s) is less than 14 characters",
                          self.vend_assign_inv_nbr,
                          self.addr_select_vend_nbr)
            self.errors += 1
        return self.errors

    def validate_line(self, pmt_tax_cd):
        """
        Do checks on apfeed before generating by line
        Will update the number of errors
        """

        # Tax code has requirements if it is not 0
        if pmt_tax_cd == 'B' or pmt_tax_cd == 'C':
            if (not self.goods_received_dt.strip()
                    or not self.org_shp_zip_cd.strip()
                    or not self.org_shp_state_cd.strip()):
                logging.error("Conditionally required field is empty:"
                              "GOODS_RECEIVED_DT, ORG_SHP_ZIP_CD and "
                              "ORG_SHP_STATE_CD required when PMT_TAX_CD"
                              " is B or C - for invoice: %s", self.vend_assign_inv_nbr)
                self.errors += 1
        return self.errors

    def __str__(self):
        """To string format which can be printed

        Called after all of the invoices have been successfully formatted as str
        """
        out = "**HEADERLGGENERALLIBRARY %s\n" % self.now.strftime(
            "%Y%m%d%H%M%S"
        )
        out += "\n".join(self.invoices)
        out += "\n**TRAILERGENERALLIBRARY %06d" % self.count
        return out


def xml_to_invoices(input_file):
    """Uses XML standard library to parse input xml into ElementTrees (ET).

    ETs will then be formatted to string.

    Args:
        input_file (str): File path of XML output file from Alma.

    Returns:
        List: List of invoices represented as ElementTrees.

    """
    # NSP: Namespace defined below imports
    out = []
    with open(input_file, 'r') as xfh:
        data = ET.parse(xfh).getroot()
        for inv in data.findall(".//exl:invoice", NSP):
            out.append(inv)
    return out


# pylint: disable=C0103
if __name__ == "__main__":
    # Constants
    mytime = int(time.time())
    cwd = os.getcwd()

    # parse command line arguments
    parser = argparse.ArgumentParser(
        description='Import/Translate/Upload XML files to Apfeed.'
    )

    parser.add_argument('-i', '--input-file')
    parser.add_argument(
        '-l', '--log-file',
        default="xml_to_apfeed.%d.log" % mytime,
        help='logfile name (default: xml_to_apfeed.<time>.log)'
    )
    parser.add_argument(
        '--log-dir',
        default=os.path.join(cwd, "logs"),
        help='log directory (default: <cwd>/logs)'
    )
    parser.add_argument(
        '--log-level',
        default='INFO',
        help='log level of written log (default: INFO) Possible '
             '[DEBUG, INFO, WARNING, ERROR, CRITICAL]'
    )
    parser.add_argument(
        '-a', '--apfeed-file',
        default="apfeed.LG.%s" % datetime.datetime.now().strftime(
            '%Y%m%d%H%M%S'
        ),
        help='output file name of apfeed file (default:apfeed.LG.<time>)'
    )
    parser.add_argument(
        '-x', '--xml-dir',
        default=os.path.join(cwd, "xml"),
        help='Directory where it will try to ingest'
             ' the xml files from. (default:<cwd>/xml)')
    parser.add_argument(
        '--archive-dir',
        default=os.path.join(cwd, "archive"),
        help='Directory where xml_to_apfeed will'
        ' archive xmls and apfeed (default:<cwd>/archive)'
    )
    parser.add_argument(
        '--apfeed-dir',
        default=os.path.join(cwd, "apfeed"),
        help='Directory where xml_to_apfeed will'
        ' create apfeed file before upload(default:<cwd>/apfeed)'
    )
    parser.add_argument(
        '--report-dir',
        default=os.path.join(cwd, "reports"),
        help='Directory where xml_to_apfeed will'
        ' create a report csv for External IDs(default:<cwd>/reports)'
    )
    args = parser.parse_args()

    # Create and setup logging
    latest_log = os.path.join(args.log_dir, "xml_to_apfeed.latest.log")
    if not os.path.isdir(args.log_dir):
        os.mkdir(args.log_dir)
    log_file_path = os.path.join(args.log_dir, args.log_file)

    # Create and setup apfeed dir
    apfeed_dir = args.apfeed_dir
    if not os.path.isdir(apfeed_dir):
        os.mkdir(apfeed_dir)
    apfeed_file_path = os.path.join(apfeed_dir, args.apfeed_file)

    # Create and setup archive
    archive_dir = args.archive_dir
    if not os.path.isdir(archive_dir):
        os.mkdir(archive_dir)
    xml_arch_dir = os.path.join(archive_dir, "xml")
    if not os.path.isdir(xml_arch_dir):
        os.mkdir(xml_arch_dir)

    numeric_level = getattr(logging, args.log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % args.log_level)
    logging.basicConfig(filename=log_file_path,
                        level=numeric_level,
                        format="[%(levelname)-5.5s] %(message)s")
    logging.getLogger().addHandler(logging.StreamHandler())

    # If input file is not selected we check all files in xml/
    xmls = []
    if args.input_file is None:
        xml_dir = args.xml_dir
        for xml_file in os.listdir(xml_dir):
            if xml_file.endswith(".xml"):
                xmls.append(os.path.join(xml_dir, xml_file))
    else:
        xmls = [args.input_file]

    if not xmls:
        logging.info("No XMLs Dectected")
        sys.exit(0)

    # Start building Apfeed file
    apf = Apfeed()

    for xml in xmls:
        logging.info("Processing %s", xml)
        # Start reading tpyhe xml file for invoices
        invoices = xml_to_invoices(xml)

        # Add invoices to apfeed file
        for invoice in invoices:
            apf.add_inv(invoice)

    if apf.errors > 0:
        logging.info("Not creating apfeed because there were %d errors", apf.errors)
        sys.exit(1)
    else:
        # Write the file
        logging.info("Writing %s", apfeed_file_path)
        with open(apfeed_file_path, 'w') as apfeed_file:
            apfeed_file.write(str(apf))

    # Generate report
    if not os.path.isdir(args.report_dir):
        os.mkdir(args.report_dir)
    export_id_file = os.path.join(args.report_dir, "external_id.%d.csv" % mytime)
    logging.info("Creating CSV %s", export_id_file)
    logging.info("External ID Totals")
    with open(export_id_file, 'wb') as report_file:
        w = csv.writer(report_file)
        w.writerow(('External ID', 'Use Tax', 'Total'))
        logging.info("External ID : Use Tax | Total")
        for k in apf.eids:
            logging.info("%s: $%.2f | $%.2f", k, apf.eids[k]['tax'], apf.eids[k]['amt'])
            w.writerow((k, "%.2f" % apf.eids[k]['tax'], "%.2f" % apf.eids[k]['amt']))

    invoice_tax_file = os.path.join(args.report_dir, "invoice_tax.%d.csv" % mytime)
    logging.info("Creating CSV %s", invoice_tax_file)
    with open(invoice_tax_file, 'wb') as report_file:
        w = csv.writer(report_file)
        w.writerow(('Invoice', 'Use Tax Total', 'Amount Total'))
        for k in sorted(apf.invs):
            w.writerow((k, "%.2f" % apf.invs[k]['tax'], "%.2f" % apf.invs[k]['total']))

    # move XML to archive
    for xml in xmls:
        logging.info("Moving %s to archive", xml)
        shutil.move(xml, xml_arch_dir)

    # set current log as latest log
    if os.path.lexists(latest_log):
        os.unlink(latest_log)
    os.symlink(log_file_path, latest_log)

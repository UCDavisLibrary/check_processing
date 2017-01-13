# Author: Alexander Lin (alxlin@ucdavis.edu)
# Python version of xml_to_apfeed.php
# Inputs: XMLs
# Output: Apfeeds
# Reads exported XML generated by Alma for ERP finanical system
# Creates an apfeed file and uploads it

import argparse
import ConfigParser
import datetime
import logging
import os
import paramiko
import shutil
import time
import xml.etree.ElementTree as ET


from scp import SCPClient
from pprint import pprint

# Read config from config.cfg
config = ConfigParser.ConfigParser()
config.readfp(open('config.ini'))

ns = {'exl': 'http://com/exlibris/repository/acq/invoice/xmlbeans'}

def strstr(haystack, needle):
    pos = haystack.upper().find(needle.upper())
    if pos < 0: # not found
        return haystack
    else:
        return haystack[:pos] + "}"


def createSSHClient(server, user, key_file):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(server, username=user, key_filename=key_file)
    return client


class apfeed:
    """Class to model what apfeed should be generated"""
    def __init__(self):
        """Initialization"""
        self.now = datetime.datetime.now()
        self.count = 0
        self.invoices = []
        self.org_doc_nbr = int(config.get("apfeed","org_doc_nbr"))
        self.emp_ind = 'N'

    def add_inv(self, inv):
        """
        Add invoice to apfeed file
        Apfeed file format as follows:
        'GENERALLIBRARY AAAAAAAAAAAAAABBBBBBBCDDDDDDDDDDDEEEEEEEEEEEEEEFFFFFFFFGGGGGGGGGGGGGG                                                                                                                                                                                                                               HHHHHHHHHIIIIIIIIII JJK     LLLLLLLLMN000183 MAINBKS     9200             POL}    C000000002950NN                                        '
        Values  | Position  | Description
        A       | 15 - 29   | time now in %Y%m%d%H%M%S
        B       | 29 - 36   | ORG_DOC_NBR
        C       | 36 - 37   | EMP_IND
        D       | 37 - 47   | VEND_CODE
        E       | 47 - 62   | VEND_ASSIGN_INV_NBR
        F       | 62 - 70   | VEND_ASSIGN_INV_DATE
        G       | 70 - 84   | ADDR_SELECT_VEND_NBR
        H       | 308 - 316 | GOODS_RECEIVED_DT
        I       | 316 - 327 | ORG_SHP_ZIP_CD
        J       | 327 - 329 | ORG_SHP_STATE_CD
        K       | 329 - 330 | PMT_GRP_CD
        L       | 335 - 343 | SCHEDULED_PMT_DT
        M       | 343 - 344 | PMT_NON_CHECK_IND
        N       | 344 - 345 | FIN_COA_CD


        """
        self.org_doc_nbr += 1
        # Foreach of the invoice lines
        vend_nbr = inv.find("exl:vendor_additional_code", ns).text
        vend_assign_inv_nbr = inv.find("exl:invoice_number", ns).text
        vend_assign_inv_date = datetime.datetime.strptime(inv.find("exl:invoice_date", ns).text, "%m/%d/%Y")
        addr_select_vend_nbr = inv.find("exl:vendor_additional_code", ns).text.replace(" ", "")
        pmt_remit_nm = " " * 40
        pmt_remit_line_1_addr = " " * 40
        pmt_remit_line_2_addr = " " * 40
        pmt_remit_line_3_addr = " " * 40
        pmt_remit_city_nm = " " * 40
        pmt_remit_st_cd = " " * 2
        pmt_remit_zip_cd = " " * 11
        pmt_remit_cntry_cd = " " * 2
        vend_st_res_ind = " "
        inv_received_dt = " " * 8
        note_list = inv.find("exl:noteList", ns)
        if note_list is None:
            create_dt = inv.find("exl:owneredEntity/exl:creationDate", ns)
            if create_dt is None:
                goods_received_dt = " " * 8
            else:
                goods_received_dt = create_dt.text
            attachment_req_ind = 'N'
        else:
            goods_received_dt = note_list.find("exl:note/exl:owneredEntity/exl:creationDate",ns).text
            if note_list.find("exl:note/exl:content", ns).text == "ATTACHMENT":
                attachment_req_ind = 'Y'
            else:
                attachment_req_ind = 'N'
        org_shp_zip_cd = config.get("apfeed", "org_shp_zip_cd")
        org_shp_state_cd = config.get("apfeed", "org_shp_state_cd")
        pmt_grp_cd = config.get("apfeed", "pmt_grp_cd")
        inv_fob_cd = " " * 2
        disc_term_cd = " " * 2
        scheduled_pmt_dt = self.now.strftime("%Y%m%d")
        pmt_non_check_ind = config.get("apfeed", "pmt_non_check_ind")
        fin_coa_cd = config.get("apfeed", "fin_coa_cd")
        sub_acct_nbr = " " * 5
        fin_object_cd = config.get('apfeed', 'fin_object_cd')
        fin_sub_obj_cd = " " * 3
        project_cd = " " * 10
        pmt_tax_cd = 'A' if float(inv.find("exl:vat_info/exl:vat_amount", ns).text) > 0 else '0'
        apply_disc_ind = config.get('apfeed', 'apply_disc_ind')
        eft_override_ind = config.get('apfeed', 'eft_override_ind')
        ap_pmt_purpose_desc = " " * 120

        for inv_line in inv.findall("./exl:invoice_line_list/exl:invoice_line", ns):
            pmt_line_nbr = int(inv_line.find("exl:line_number", ns).text)
            account_nbr = inv_line.find("exl:fund_info_list/exl:fund_info/exl:external_id", ns).text
            po_line_nbr = inv_line.find("exl:po_line_info/exl:po_line_number", ns)
            if po_line_nbr is None:
                org_reference_id = " " * 8
            else:
                org_reference_id = strstr(po_line_nbr.text, '-')
            pmt_amt = float(inv_line.find("exl:fund_info_list/exl:fund_info/exl:amount/exl:sum", ns).text) * 100
            note = inv_line.find("exl:note", ns)
            if note is not None and note.text == "UTAX":
                pmt_tax_cd = 'C'
            istr = "GENERALLIBRARY %s%07d%c%s%-15s%s%s%s%s%s%s%s%s%s%s%s%s%-8s%s %s%s%s%s %s%c%c%05d%s %s%s%s%s%s%-8s%c%.012d%c%c%s" % (
                                        self.now.strftime("%Y%m%d%H%M%S"),
                                        self.org_doc_nbr,
                                        self.emp_ind,
                                        vend_nbr[0:10],
                                        vend_assign_inv_nbr[0:15],
                                        vend_assign_inv_date.strftime("%Y%m%d"),
                                        addr_select_vend_nbr,
                                        pmt_remit_nm,
                                        pmt_remit_line_1_addr,
                                        pmt_remit_line_2_addr,
                                        pmt_remit_line_3_addr,
                                        pmt_remit_city_nm,
                                        pmt_remit_st_cd,
                                        pmt_remit_zip_cd,
                                        pmt_remit_cntry_cd,
                                        vend_st_res_ind,
                                        inv_received_dt,
                                        goods_received_dt[0:8],
                                        org_shp_zip_cd[0:11],
                                        org_shp_state_cd[0:2],
                                        pmt_grp_cd,
                                        inv_fob_cd,
                                        disc_term_cd,
                                        scheduled_pmt_dt,
                                        pmt_non_check_ind,
                                        attachment_req_ind,
                                        pmt_line_nbr,
                                        fin_coa_cd,
                                        account_nbr[0:7],
                                        sub_acct_nbr,
                                        fin_object_cd,
                                        fin_sub_obj_cd,
                                        project_cd,
                                        org_reference_id[0:8],
                                        pmt_tax_cd,
                                        pmt_amt,
                                        apply_disc_ind,
                                        eft_override_ind,
                                        ap_pmt_purpose_desc
                                        )
            self.invoices.append(istr)
            self.count += 1

    def to_string(self):
        """To string format which can be printed"""
        out = "**HEADERLGGENERALLIBRARY %s\n" % self.now.strftime("%Y%m%d%H%M%S")
        out += "\n".join(self.invoices)
        out += "\n**TRAILERGENERALLIBRARY %06d" % self.count
        return out

def xml_to_invoices(input_file):
    out = []
    with open(input_file, 'r') as xml_file:
        data = ET.parse(xml_file).getroot()
        for inv in data.findall(".//exl:invoice", ns):
            out.append(inv)
    return out


if __name__ == "__main__":
    # Constants
    mytime = int(time.time())
    cwd = os.getcwd()
    log_dir = os.path.join(cwd, "logs")
    latest_log = os.path.join(log_dir, "xml_to_apfeed.latest.log")

    # parse command line arguments
    parser = argparse.ArgumentParser(description='Import/Translate/Upload XML files to text files. Transfer those files to the target server via SCP for processing by Finance.')

    parser.add_argument('-i', '--input-file')
    parser.add_argument('-l', '--log-file',
                        default="xml_to_apfeed.%d.log" % mytime,
                        help='logfile name (default: xml_to_apfeef.<time>.log)')
    parser.add_argument('--log-level',
                        default='INFO',
                        help='log level of written log (default: INFO) Possible [DEBUG, INFO, WARNING, ERROR, CRITICAL]')
    parser.add_argument('-a', '--apfeed-file',
                         default="apfeed.LG.%s" %  datetime.datetime.now().strftime('%Y%m%d%H%M%S'),
                         help='output file name of apfeed file (default:apfeed.LG.<time>)')
    parser.add_argument('--no-upload',
                        action='store_true',
                        default=False)
    args = parser.parse_args()

    # Create and setup logging
    if not os.path.isdir(log_dir):
        os.mkdir(log_dir)
    log_file_path = os.path.join(log_dir, args.log_file)

    # Create and setup apfeed dir
    apfeed_dir = os.path.join(cwd, "apfeed")
    if not os.path.isdir(apfeed_dir):
        os.mkdir(apfeed_dir)
    apfeed_file_path = os.path.join(apfeed_dir, args.apfeed_file)

    # Create and setup archive
    archive_dir = os.path.join(cwd, "archive")
    if not os.path.isdir(archive_dir):
        os.mkdir(archive_dir)
    xml_arch_dir = os.path.join(archive_dir, "xml")
    if not os.path.isdir(xml_arch_dir):
        os.mkdir(xml_arch_dir)

    numeric_level = getattr(logging, args.log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % args.log_level)
    logging.basicConfig(filename=log_file_path,
                        level=numeric_level)

    # If input file is not selected we check all files in xml/
    xmls = []
    if args.input_file is None:
        xml_dir = os.path.join(cwd, "xml")
        for file in os.listdir(xml_dir):
            if file.endswith(".xml"):
                xmls.append(os.path.join(xml_dir, file))
    else:
        xmls = [args.input_file]
    # Start building Apfeed file
    apf = apfeed()
    for xml in xmls:
        logging.info("Processing %s" % xml)
        # Start reading the xml file for invoices
        invoices = xml_to_invoices(xml)

        # Add invoices to apfeed file
        for inv in invoices:
            apf.add_inv(inv)

        # Move XML to archive/xml
        shutil.move(xml, xml_arch_dir)

    # Write the file
    logging.info("Writing %s" % apfeed_file_path)
    with open(apfeed_file_path, 'wb') as apfeed_file:
        apfeed_file.write(apf.to_string())

    # Upload to server
    server = config.get("apfeed_scp_out", "server")
    user = config.get("apfeed_scp_out", "user")
    private_key =config.get("apfeed_scp_out", "private_key")


    if not args.no_upload:
        logging.info("Uploading via SCP")
        ssh = createSSHClient(server, user, private_key)
        scp = SCPClient(ssh.get_transport())
        scp.put(apfeed_file_path)

    # Update config.ini for org_doc_nbr
    config.set("apfeed","org_doc_nbr",apf.org_doc_nbr)
    with open("config.ini", 'wb') as config_file:
        config.write(config_file)

    # set current log as latest log
    if os.path.lexists(latest_log):
        os.unlink(latest_log)
    os.symlink(log_file_path, latest_log)

import ConfigParser
import datetime
import logging
import sys
import os
import unittest
import xml.etree.ElementTree as ET

sys.path.append("./..")
import xml_to_apfeed
from pprint import pprint

logging.disable(logging.CRITICAL)
cwd = os.getcwd()
ns = {'exl': 'http://com/exlibris/repository/acq/invoice/xmlbeans'}

# Test files
test_dir = os.path.join(cwd, "test")
xml_dir = os.path.join(test_dir, "xml")
apfeed_dir = os.path.join(test_dir, "apfeed")
test_xml = os.path.join(xml_dir, "test.xml")


class TestBase(unittest.TestCase):
    def test_xml_import(self):
        """Test that ingesting xml to invoice was done correctly"""
        invs = xml_to_apfeed.xml_to_invoices(test_xml)
        self.assertIsNotNone(invs, "Invoices were not read properly by XML parser")
        self.assertIs(len(invs), 4, "Incorrect number of invoices ingested: {0} Expecting 4".format(len(invs)))
        self.assertEquals(invs[0].find("exl:invoice_number", ns).text, "0201821", "Incorrect invoice number: got({0}), expecting '0201821'".format(invs[0].find("exl:invoice_number", ns).text))

    def inv_str(self, s, start, end, val, tag):
        self.assertEquals(s[start:end], val, "Char %d-%d got '%s', expecting '%s', tag '%s'" % (start, end, s[start:end], val, tag))

    def test_apfeed_conversion(self):
        """Test that we properly convert xml to apfeed"""
        apf = xml_to_apfeed.Apfeed()
        invs = xml_to_apfeed.xml_to_invoices(test_xml)
        org_doc_nbr = apf.org_doc_nbr
        apf.add_inv(invs[0])
        now = datetime.datetime.now()

        self.assertEquals(apf.org_doc_nbr, org_doc_nbr + 1, "Adding inv not incrementing org_doc_nbr")
        self.assertEquals(apf.count, 3, "Incorrect count number: got(%d), expecting 3" % apf.count)
        istr = apf.invoices[0]
        self.inv_str(istr, 0, 15, 'GENERALLIBRARY ', 'Header')
        self.inv_str(istr, 15, 29, apf.now.strftime("%Y%m%d%H%M%S"), 'Time now')
        self.inv_str(istr, 29, 36, "%s" % apf.org_doc_nbr,'ORG_DOC_NBR')
        self.inv_str(istr, 36, 37, 'N', 'EMP_IND')
        self.inv_str(istr, 37, 47, '0000002413', 'VEND_CODE')
        self.inv_str(istr, 47, 62, '0201821        ', 'VEND_ASSIGN_INV_NBR')
        self.inv_str(istr, 62, 70, '20161125', 'VEND_ASSIGN_INV_DATE')
        self.inv_str(istr, 70, 84, '00000024130002', 'ADDR_SELECT_VEND_NBR')
        self.inv_str(istr, 308, 316, '20170104', 'GOODS_RECEIVED_DT')
        self.inv_str(istr, 316, 327, '95616-5292 ', 'ORG_SHP_ZIP_CD')
        self.inv_str(istr, 327, 329, 'CA', 'ORG_SHP_STATE_CD')
        self.inv_str(istr, 329, 330, '2', 'PMT_GRP_CD')
        self.inv_str(istr, 335, 343, now.strftime("%Y%m%d"), 'SCHEDULED_PMT_DT')
        self.inv_str(istr, 343, 344, 'N', 'PMT_NON_CHECK_IND')
        self.inv_str(istr, 344, 345, 'N', 'ATTACHMENT_REQ_IND')
        self.inv_str(istr, 345, 350, '00018', 'PMT_LINE_NBR')
        self.inv_str(istr, 350, 351, '3', 'FIN_COA_CD')
        self.inv_str(istr, 352, 359, 'MAINBKS', 'ACCOUNT_NBR')
        self.inv_str(istr, 364, 368, '9200', 'FIN_OBJECT_CD')
        self.inv_str(istr, 381, 389, 'POL}    ', 'ORG_REFERENCE_ID')
        self.inv_str(istr, 389, 390, 'C', 'PMT_TAX_CD')
        self.inv_str(istr, 390, 402, '000000002950', 'PMT_AMT')
        self.inv_str(istr, 402, 403, 'N', 'APPLY_DISC_IND')
        self.inv_str(istr, 403, 404, 'N', 'EFT_OVERRIDE_IND')

        istr = apf.invoices[2]
        self.assertEquals(istr[389:390], 'C', "If invoice line note starts with UTAX then it should be set as UTAX");

        apf.add_inv(invs[1])
        istr = apf.invoices[3]
        self.inv_str(istr, 0, 15, 'GENERALLIBRARY ', 'Header')
        self.inv_str(istr, 15, 29, apf.now.strftime("%Y%m%d%H%M%S"), 'Time now')
        self.inv_str(istr, 29, 36, "%s" % apf.org_doc_nbr,'ORG_DOC_NBR')
        self.inv_str(istr, 36, 37, 'N', 'EMP_IND')
        self.inv_str(istr, 37, 47, '0000008563', 'VEND_CODE')
        self.inv_str(istr, 47, 62, '895350         ', 'VEND_ASSIGN_INV_NBR')
        self.inv_str(istr, 62, 70, '20161208', 'VEND_ASSIGN_INV_DATE')
        self.inv_str(istr, 70, 84, '00000085630005', 'ADDR_SELECT_VEND_NBR')
        self.inv_str(istr, 308, 316, '20161215', 'GOODS_RECEIVED_DT')
        self.inv_str(istr, 316, 327, '95616-5292 ', 'ORG_SHP_ZIP_CD')
        self.inv_str(istr, 327, 329, 'CA', 'ORG_SHP_STATE_CD')
        self.inv_str(istr, 329, 330, '2', 'PMT_GRP_CD')
        self.inv_str(istr, 335, 343, now.strftime("%Y%m%d"), 'SCHEDULED_PMT_DT')
        self.inv_str(istr, 343, 344, 'N', 'PMT_NON_CHECK_IND')
        self.inv_str(istr, 344, 345, 'N', 'ATTACHMENT_REQ_IND')
        self.inv_str(istr, 345, 350, '00001', 'PMT_LINE_NBR')
        self.inv_str(istr, 350, 351, '3', 'FIN_COA_CD')
        self.inv_str(istr, 352, 359, 'MAINBKS', 'ACCOUNT_NBR')
        self.inv_str(istr, 364, 368, '9200', 'FIN_OBJECT_CD')
        self.inv_str(istr, 381, 389, 'POL}    ', 'ORG_REFERENCE_ID')
        self.inv_str(istr, 389, 390, '0', 'PMT_TAX_CD')
        self.inv_str(istr, 390, 402, '000000003256', 'PMT_AMT')
        self.inv_str(istr, 402, 403, 'N', 'APPLY_DISC_IND')
        self.inv_str(istr, 403, 404, 'N', 'EFT_OVERRIDE_IND')

        self.assertEquals(str(apf).count("\n"), 10, "apf  did not have the correct number of lines (got: %d, expecting: 10)" % str(apf).count("\n"))

        apf.add_inv(invs[2])

        apf.add_inv(invs[3])
        self.inv_str(apf.invoices[10], 390, 402, '-00000012000', 'Negative PMT_AMT needs to work')

        inv = invs[0]
        tomorrow = apf.now + datetime.timedelta(days=1)
        inv.find("exl:invoice_date",ns).text = tomorrow.strftime("%m/%d/%Y")
        apf.add_inv(inv)
        self.assertEquals(apf.count, 11, "Does not include apfeeds that are in the future")

    def test_utax(self):
        """Test that we properly convert xml to apfeed"""
        apf = xml_to_apfeed.Apfeed()
        invs = xml_to_apfeed.xml_to_invoices(os.path.join(xml_dir, "test_utax.xml"))
        org_doc_nbr = apf.org_doc_nbr
        for inv in invs:
            apf.add_inv(inv)
        now = datetime.datetime.now()

        # test UTAX invoice/invoice line and NUTAX
        self.assertEquals(apf.invoices[0][389:390], '0', "UTAX should default to invoices if invoice line doesn't have UTAX");

        self.assertEquals(apf.invoices[1][389:390], 'C', "UTAX set in invoice line note");

        self.assertEquals(apf.invoices[2][389:390], 'C', "UTAX set in invoice note");

        self.assertEquals(apf.invoices[3][389:390], '0', "UTAX set in invoice note but NUTAX set in line");

        # testing ATTACH
        self.inv_str(apf.invoices[4], 344, 345, 'Y', 'ATTACHMENT_REQ_IND')
        self.assertEquals(apf.invoices[4][389:390], 'C', "UTAX set in invoice note");

        self.inv_str(apf.invoices[5], 344, 345, 'Y', 'ATTACHMENT_REQ_IND')

        self.assertEquals(apf.invoices[5][389:390], '0', "Just ATTACH set in invoice");

        # testing ATAX
        self.inv_str(apf.invoices[6], 344, 345, 'Y', 'ATTACHMENT_REQ_IND')
        self.assertEquals(apf.invoices[6][389:390], '0', "NUTAX set in invoice note");

        self.inv_str(apf.invoices[7], 344, 345, 'Y', 'ATTACHMENT_REQ_IND')

        self.assertEquals(apf.invoices[7][389:390], 'C', "Just ATAX set in invoice");

if __name__ == '__main__':
    unittest.main()

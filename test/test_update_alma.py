import sys
import os
import unittest
import xml.etree.ElementTree as ET

sys.path.append("./..")
import update_alma

from pprint import pprint

cwd = os.getcwd()
ns = {'exl': 'http://com/exlibris/repository/acq/xmlbeans/'}
nse = "http://com/exlibris/repository/acq/xmlbeans"

# Test files
test_dir = os.path.join(cwd, "test")

class Test_Update_Alma(unittest.TestCase):
    def test_get_waiting_invoices(self):
        invoices, nums, vendors = update_alma.get_waiting_invoices(None)
        for inv in invoices.itervalues():
            self.assertEquals(inv['invoice_workflow_status']['value'], 'Ready to be Paid', "%s status is not 'Ready to be Paid'" % inv['number'])

    def test_kfs_query(self):
        nums = ['US10046263']
        vendors = {}
        cur = update_alma.kfs_query(nums)
        kfs_hash = update_alma.process_query(cur, vendors)
        test_input_xml = os.path.join(test_dir, "xml", "test.input.xml")
        test_input = ET.parse(test_input_xml).getroot()
        invoice_list = test_input.find("./", ns)
        for inv in invoice_list.findall("./", ns):
            self.assertEquals(float(inv.find("{%s}voucher_amount/{%s}sum" % (nse, nse)).text), float(kfs_hash['US10046263']['pay_amt']), "KFS query mismatched our own test xml in pay amount %f != %f" % (float(inv.find("{%s}voucher_amount/{%s}sum" % (nse, nse)).text), float(kfs_hash['US10046263']['pay_amt'])))
            self.assertEquals(inv.find("{%s}payment_voucher_date" %nse).text, kfs_hash['US10046263']['pay_date'], "KFS query mismatched our own test xml in pay date %s != %s" % (inv.find("{%s}payment_voucher_date" %nse).text, kfs_hash['US10046263']['pay_date']))

    def test_vendor_query(self):
        code = update_alma.fetch_vendor_code('YANK')
        self.assertEquals(code[1], '8563-0', "Vendor query grabbed incorrect vendor code (expecting: '8563-0', got: '%s'" % str(code))

    def test_process_query(self):
        cur = [['43529685','8563-0','YANKEE BOOK PEDDLER INC','10076','C10647617','295.74','20170321','DV']]
        vendors = {}
        base = {'check_num': 'C10647617',
           'doc_num': '43529685',
           'doc_type': 'DV',
           'num': '10076',
           'pay_amt': '295.74',
           'pay_date': '20170321',
           'vendor_id': '8563-0',
           'vendor_name': 'YANKEE BOOK PEDDLER INC'}
        invs = update_alma.process_query(cur, vendors)
        self.assertEquals(invs['10076'], base , "process query should work even if vendor is not specified")
        cur = [['43529685','8563-0','YANKEE BOOK PEDDLER INC','10076','C10647617','295.74','20170321','DV'], ['43529685','8563-0','YANKEE BOOK PEDDLER INC','10076','C10647617','295.74','20170321','DV']]
        invs = update_alma.process_query(cur, vendors)
        self.assertEquals(invs['10076'], base , "process query should handle duplicates")

        cur = [['43529685','853-0','YANKEE BOOK PEDDLER INC','10076','C10647617','295.74','20170321','DV'], ['43529685','8563-0','YANKEE BOOK PEDDLER INC','10076','C10647617','295.74','20170321','DV']]
        invs = update_alma.process_query(cur, vendors)
        self.assertEquals(invs, {} , "process_query if there are two with different vendor id don't put them")

        vendors = {'10076': '8563-0'}
        cur = [['43529685','853-0','YANKEE BOOK PEDDLER INC','10076','C10647617','295.74','20170321','DV'], ['43529685','8563-0','YANKEE BOOK PEDDLER INC','10076','C10647617','295.74','20170321','DV']]
        invs = update_alma.process_query(cur, vendors)
        self.assertEquals(invs['10076'], base , "process_query picks out the correct one because of vendor id")

    def test_erp_xml(self):
        erp  = update_alma.ErpXml()
        self.assertEquals(erp.to_string(), '<?xml version="1.0" encoding="UTF-8"?>\n<payment_confirmation_data xmlns="http://com/exlibris/repository/acq/xmlbeans">\n   <invoice_list/>\n</payment_confirmation_data>\n', "ERP XML intialization string is incorrect")
        inv_num = 'US10046263'
        alma = {'id' : '4829238050003126',
                'invoice_date' : '2016-12-05',
                'vendor' : { 'value' : 'PRQST'}}
        kfs = {'pay_date' : '20161220',
               'check_num' : 'V40047088',
               'pay_amt' : 3810,
               'doc_num' : '42497084',
               'vendor_id' : '122172-0',
               'vendor_name' : 'PROQUEST LP'}
        erp.add_paid_invoice(inv_num, alma, kfs)
        self.assertEquals(erp.to_string(),'<?xml version="1.0" encoding="UTF-8"?>\n<payment_confirmation_data xmlns="http://com/exlibris/repository/acq/xmlbeans">\n   <invoice_list>\n      <invoice>\n         <invoice_number>US10046263</invoice_number>\n         <unique_identifier>4829238050003126</unique_identifier>\n         <invoice_date>20161205</invoice_date>\n         <vendor_code>PRQST</vendor_code>\n         <payment_status>PAID</payment_status>\n         <payment_voucher_date>20161220</payment_voucher_date>\n         <payment_voucher_number>V40047088</payment_voucher_number>\n         <voucher_amount>\n            <currency>USD</currency>\n            <sum>3810</sum>\n         </voucher_amount>\n      </invoice>\n   </invoice_list>\n</payment_confirmation_data>\n', "Added invoice to ERP XML failed")


if __name__ == '__main__':
    unittest.main()

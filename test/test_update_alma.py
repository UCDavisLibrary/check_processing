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
        invoices, nums = update_alma.get_waiting_invoices(None)
        for inv in invoices.itervalues():
            self.assertEquals(inv['invoice_workflow_status']['value'], 'Ready to be Paid', "%s status is not 'Ready to be Paid'" % inv['number'])

    def test_kfs_query(self):
        nums = ['US10046263']
        kfs_hash = update_alma.kfs_query(nums)
        test_input_xml = os.path.join(test_dir, "xml", "test.input.xml")
        test_input = ET.parse(test_input_xml).getroot()
        invoice_list = test_input.find("./", ns)
        for inv in invoice_list.findall("./", ns):
            self.assertEquals(float(inv.find("{%s}voucher_amount/{%s}sum" % (nse, nse)).text), float(kfs_hash['US10046263']['pay_amt']), "KFS query mismatched our own test xml in pay amount %f != %f" % (float(inv.find("{%s}voucher_amount/{%s}sum" % (nse, nse)).text), float(kfs_hash['US10046263']['pay_amt'])))
            self.assertEquals(inv.find("{%s}payment_voucher_date" %nse).text, kfs_hash['US10046263']['pay_date'], "KFS query mismatched our own test xml in pay date %s != %s" % (inv.find("{%s}payment_voucher_date" %nse).text, kfs_hash['US10046263']['pay_date']))

    def test_erp_xml(self):
        erp  = update_alma.ErpXml()
        self.assertEquals(erp.to_string(), '<?xml version="1.0" encoding="UTF-8"?>\n<payment_confirmation_data xmlns="http://com/exlibris/repository/acq/xmlbeans">\n   <invoice_list/>\n</payment_confirmation_data>\n', "ERP XML intialization string is incorrect")
        inv_num = 'US10046263'
        alma = {'id' : '4829238050003126',
                'invoice_date' : '2016-12-05',
                'vendor' : { 'value' : 'PRQST'}}
        kfs = {'pay_date' : '20161220',
               'check_num' : 'V40047088',
               'pay_amt' : 3810}
        erp.add_paid_invoice(inv_num, alma, kfs)
        self.assertEquals(erp.to_string(),'<?xml version="1.0" encoding="UTF-8"?>\n<payment_confirmation_data xmlns="http://com/exlibris/repository/acq/xmlbeans">\n   <invoice_list>\n      <invoice>\n         <invoice_number>US10046263</invoice_number>\n         <unique_identifier>4829238050003126</unique_identifier>\n         <invoice_date>20161205</invoice_date>\n         <vendor_code>PRQST</vendor_code>\n         <payment_status>PAID</payment_status>\n         <payment_voucher_date>20161220</payment_voucher_date>\n         <payment_voucher_number>V40047088</payment_voucher_number>\n         <voucher_amount>\n            <currency>USD</currency>\n            <sum>3810</sum>\n         </voucher_amount>\n      </invoice>\n   </invoice_list>\n</payment_confirmation_data>\n', "Added invoice to ERP XML failed")

if __name__ == '__main__':
    unittest.main()

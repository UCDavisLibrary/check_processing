import ConfigParser
import datetime
import logging
import sys
import os
import unittest
import xml.etree.ElementTree as ET

sys.path.append("./..")
import upload_apfeed
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
    def test_scp(self):
        # Read config from config.cfg
        config = ConfigParser.ConfigParser()
        config.readfp(open('config.ini'))
        server = config.get("apfeed_scp_out", "server")
        user = config.get("apfeed_scp_out", "user")
        private_key =config.get("apfeed_scp_out", "private_key")
        self.assertIsNotNone(upload_apfeed.create_ssh_client(server, user, private_key), "SSH Client failed to create")

if __name__ == '__main__':
    unittest.main()

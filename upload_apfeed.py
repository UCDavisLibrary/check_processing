#!/usr/bin/env python2.7

"""
Author: Alexander Lin (alxlin@ucdavis.edu)
upload_apfeed.py
Inputs: Apfeed
Output: None
Uploads apfeed to KFS
Also can be used to delete apfeeds and decrement org_doc_nbr
"""
import argparse
import ConfigParser
import logging
import os
import shutil
import sys
import time

import paramiko

from scp import SCPClient

# Read config from config.ini
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, 'config.ini')
CONFIG = ConfigParser.ConfigParser()
CONFIG.readfp(open(CONFIG_PATH))

def create_ssh_client(scp_server, scp_user, scp_key_file):
    """
    Creates SSH Client for SCP
    """
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(scp_server, username=scp_user, key_filename=scp_key_file)
    return client

# pylint: disable=C0103
if __name__ == "__main__":
    # Constants
    mytime = int(time.time())
    cwd = os.getcwd()

    # parse command line arguments
    parser = argparse.ArgumentParser(
        description=' Transfer apfeed files to the target server via'
                    ' SCP for processing by Finance.'
    )
    parser.add_argument('-f', '--apfeed_file')
    parser.add_argument(
        '-l', '--log-file',
        default="upload_apfeed.%d.log" % mytime,
        help='logfile name (default: upload_apfeed.<time>.log)'
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
        '--archive-dir',
        default=os.path.join(cwd, "archive"),
        help='Directory where xml_to_apfeed will'
        ' archive xmls and apfeed (default:<cwd>/archive)'
    )
    args = parser.parse_args()

    # Create and setup logging
    latest_log = os.path.join(args.log_dir, "upload_apfeed.latest.log")
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

    apfeed_file_path = args.apfeed_file

    # validate args
    if not apfeed_file_path:
        logging.error("upload_apfeed.py requires -f")
        sys.exit(1)
    elif not os.path.isfile(apfeed_file_path):
        logging.error("Cannot find file: %s", apfeed_file_path)
        sys.exit(1)

    # Create and setup logging
    latest_log = os.path.join(args.log_dir, "upload_apfeed.latest.log")
    if not os.path.isdir(args.log_dir):
        os.mkdir(args.log_dir)
    log_file_path = os.path.join(args.log_dir, args.log_file)
    numeric_level = getattr(logging, args.log_level.upper(), None)

    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % args.log_level)
    logging.basicConfig(filename=log_file_path,
                        level=numeric_level,
                        format="[%(levelname)-5.5s] %(message)s")
    logging.getLogger().addHandler(logging.StreamHandler())

    # Upload to server
    server = CONFIG.get("apfeed_scp_out", "server")
    user = CONFIG.get("apfeed_scp_out", "user")
    private_key = CONFIG.get("apfeed_scp_out", "private_key")

    logging.info("Uploading via SCP")
    ssh = create_ssh_client(server, user, private_key)
    scp = SCPClient(ssh.get_transport())
    scp.put(apfeed_file_path)
    logging.info("Uploaded: %s", apfeed_file_path)
    shutil.move(apfeed_file_path, apfeed_arch_dir)
    logging.info("Moved %s to %s", apfeed_file_path, apfeed_arch_dir)

    # set current log as latest log
    if os.path.lexists(latest_log):
        os.unlink(latest_log)
    os.symlink(log_file_path, latest_log)
    logging.info("Log file: %s", log_file_path)
    logging.info("Done")

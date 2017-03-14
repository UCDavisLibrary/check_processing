#!/usr/bin/env python2.7

"""
Author: Alexander Lin (alxlin@ucdavis.edu)
Inputs: Apfeed file
Output: Class dump of apfeed file
So humans can read an apfeed file
"""

import argparse
import glob
import json
import os
import sys

from pprint import pprint

# pylint: disable=C0103
if __name__ == "__main__":
    cwd = os.getcwd()

    parser = argparse.ArgumentParser(
        description='Reads and parses apfeed file'
    )

    parser.add_argument('-i', '--inv-num')
    parser.add_argument('-o', '--org-doc')
    parser.add_argument('-s', '--string')
    parser.add_argument('-f', '--file')
    parser.add_argument('-d', '--directory')
    parser.add_argument('-j', '--json', action='store_true')

    args = parser.parse_args()

    lines = []

    if args.file is not None:
        with open(args.file, 'r') as apf:
            lines = apf.readlines()
            lines = lines[1:-1]
    elif args.string is not None:
        lines = args.string.splitlines()
    elif args.directory is not None:
        if args.org_doc is None:
            print("Error directory needs to be paired with --org-doc")
            sys.exit(0)
        files = glob.glob(os.path.join(args.directory, "apfeed.LG.*"))
        files.sort(reverse=True)
        for f in files:
            with open(f, 'r') as apf:
                lines = apf.readlines()
                line = lines[1]
                # get org_doc_num
                if not line[29:36] or not line[29:36].isdigit():
                    continue
                elif int(line[29:36]) <= int(args.org_doc):
                    print("Found in file: %s" % f)
                    break

    out = []
    for line in lines:
        apfd = dict()
        apfd['time'] = line[15:29]
        apfd['org_doc_num'] = line[29:36]
        apfd['emp_ind'] = line[36:37]
        apfd['vend_code'] = line[37:47]
        apfd['vend_assign_inv_nbr'] = line[47:62]
        apfd['vend_assign_inv_date'] = line[62:70]
        apfd['addr_select_vend_nbr'] = line[70:84]
        apfd['goods_recieved_dt'] = line[308:316]
        apfd['org_shp_zip_cd'] = line[316:327]
        apfd['org_shp_state_cd'] = line[327:329]
        apfd['pmt_grp_cd'] = line[329:330]
        apfd['scheduled_pmt_dt'] = line[335:343]
        apfd['pmt_non_check_ind'] = line[343:344]
        apfd['attachment_req_ind'] = line[344:345]
        apfd['pmt_line_nbr'] = line[345:350]
        apfd['account_nbr'] = line[352:359]
        apfd['fin_object_cd'] = line[364:368]
        apfd['org_reference_id'] = line[381:389]
        apfd['pmt_tax_cd'] = line[389:390]
        apfd['pmt_amt'] = line[390:402]
        apfd['apply_disc_ind'] = line[402:403]
        apfd['eft_override_ind'] = line[403:404]

        if args.inv_num is None and args.org_doc is None:
            out.append(apfd)
        if args.inv_num is not None and apfd['vend_assign_inv_nbr'].rstrip() == args.inv_num:
            out.append(apfd)
        elif args.org_doc is not None and apfd['org_doc_num'].rstrip() == args.org_doc:
            out.append(apfd)
    out = sorted(out, key=lambda k: k['pmt_line_nbr'])
    if not out:
        print("Records not found")
        sys.exit(1);
    if args.json:
        print(json.dumps(out))
    else:
        pprint(out)

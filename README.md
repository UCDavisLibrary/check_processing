# Alma-KFS Integration Application #

Library finance maintains detailed invoice records of media acquisitions/purchases in [Alma](https://ucdavis.alma.exlibrisgroup.com/mng/action/home.do?mode=ajax), and this data must be synced with a central campus data warehouse. As a result, the overall purpose of this application is to allow non-technical library staff to safely perform ETL operations between Alma (XML and JSON) and the KFS Oracle Database (SQL) maintained by campus.

[Backend operations](https://github.com/UCDavisLibrary/check_processing#backend) were built using Python, while the [front-end](https://github.com/UCDavisLibrary/check_processing#front-end) is PHP.

## Backend ##
This repo contains just the code for the backend functionality, which is performed by the following three scripts:

**xml_to_apfeed.py**
1. Reads in variables from config file.
2. Imports XML file generated by library finance staff in Alma (default: /home/almadafis/).
3. Translates all invoice lines to a [fixed-width text format](https://github.com/UCDavisLibrary/check_processing#format) (apfeed).
4. If data [passes validations](https://github.com/UCDavisLibrary/check_processing#data-validations):
   - Exports apfeed (/apacheapfeed).
   - Exports invoice groupby reports as csv (/apachereports).
   - Moves original xml file to archive (/apachearchive/xml).
   - Marks log file as most recent log.

**upload_apfeed.py**
1. SCP uploads the apfeed text file to central campus finance server. SCP settings are in config file. <When will campus load the file?>
2. Moves apfeed to archive (/apachearchive/apfeed)
3. Updates the org_doc_nbr in the config file to match that of the last processed invoice. When xml_to_apfeed is run on the next Alma batch, this number will be loaded and incremented by 1 for each invoice processed.
4. Marks log file as most recent log.

**update_alma.py**
1. Queries Alma API for invoices waiting payments. This value is set when library finance exports the initial XML file from Alma. Requires several API calls, which are done in parallel.
2. Queries KFS Oracle Database for invoices using invoice numbers to see if they have been paid. Drops records if vendor_id is not correct or if two records have matching invoice ids. Retrieves the following fields: ```keys = ['doc_num', 'vendor_id', 'vendor_name', 'num','check_num', 'pay_amt', 'pay_date', 'doc_type']```
3. Left joins Alma and KFS data on invoice number. Logs if discrepancy in charge is more than 1% of Alma record.
4. Creates an XML which will be uploaded to Alma to update invoice statuses. Copies XML to archive (/apachearchive/alma_input). Export fields ```('Doc #', 'Vender #', 'Vender Name','Invoice #','Check #','Amount','Date')``` as check_information_report.csv. Library staff subsequently uploads XML using Alma interface ([instructions](https://bigsys.lib.ucdavis.edu/reports/check_processing/update_alma.php)).
5. Marks log file as most recent log.
### Logging: ###
Each time a script is run, it will generate an individual log file along with creating a symbolick link to the latest log (scriptname.latest.log)

### MakeFile ###
```
# Run Unit Tests
make test

# Run Coverage
make coverage

# Run pep8 style checking
make pep8

# Run Linter
make lint
```

Currently installed on bigsys.
Install to directory (default: /usr/local/alma/dafis)
Override using make install PREFIX="directory path"
Before you install please run test and lint
    make install

### File Requirements ###

#### Data Validations ####
The following data validations are performed before converting an Alma XML export to the fixed width text format required by KFS:
* Invoice date must be less than current date.
* GOODS_RECEIVED_DT, ORG_SHP_ZIP_CD and ORG_SHP_STATE_CD fields required when PMT_TAX_CD == 'B' or 'C'
The script will exit as soon as an invoice violates a validation. The script will produce no output (except for its log file).

#### Format ####
Each invoice line copied to campus server must be in the following fixed width text format:
```
'GENERALLIBRARY AAAAAAAAAAAAAABBBBBBBCDDDDDDDDDDDEEEEEEEEEEEEEE'
'FFFFFFFFGGGGGGGGGGGGGG                                          '
'               HHHHHHHHHIIIIIIIIII JJK     LLLLLLLLMNOOOOO3 '
'QQQQQQQ     RRRR          SSSSSSSSTUUUUUUUUUUUUVW             '
'                           '
```

| Values | Position | Description |
| --- | --- | --- |
| A | 15  - 29   | time now in %Y%m%d%H%M%S |
| B | 29  - 36   | ORG_DOC_NBR |
| C | 36  - 37   | EMP_IND |
| D | 37  - 47   | VEND_CODE |
| E | 47  - 62   | VEND_ASSIGN_INV_NBR |
| F | 62  - 70   | VEND_ASSIGN_INV_DATE |
| G | 70  - 84   | ADDR_SELECT_VEND_NBR |
| H | 308 - 316  | GOODS_RECEIVED_DT |
| I | 316 - 327  | ORG_SHP_ZIP_CD |
| J | 327 - 329  | ORG_SHP_STATE_CD |
| K | 329 - 330  | PMT_GRP_CD |
| L | 335 - 343  | SCHEDULED_PMT_DT |
| M | 343 - 344  | PMT_NON_CHECK_IND |
| N | 344 - 345  | ATTACHMENT_REQ_IND |
| O | 345 - 350  | PMT_LINE_NBR |
| P | 350 - 351  | FIN_COA_CD |
| Q | 352 - 359  | ACCOUNT_NBR |
| R | 364 - 368  | FIN_OBJECT_CD |
| S | 381 - 389  | ORG_REFERENCE_ID |
| T | 389 - 390  | PMT_TAX_CD |
| U | 390 - 402  | PMT_AMT |
| V | 402 - 403  | APPLY_DISC_IND |
| W | 403 - 404  | EFT_OVERRIDE_IND |

## Front End ##
Library finance staff control this application through an [interface on bigsys](https://bigsys.lib.ucdavis.edu/reports/check_processing/index.php). The primary views are:

**index.php**
* Homepage with documentation links.

**xml_to_apfeed.php**
* Allows library staff to run ```xml_to_apfeed.py```. If an apfeed was previously generated but never uploaded to campus finance servers (a file is still in staging directory ```/apacheapfeed```) then this option will not be available until user either uploads the file or deletes it.

**show_apfeed.php**
* Allows library staff to review summary reports associated with the apfeed and choose whether to upload apfeed (runs ```upload_apfeed.py```) to central finance server. If 'No' is selected, the apfeed and its reports will be deleted, and the XML file used to generate the apfeed will be returned to the staging directory (```/home/almadafis```).

**update_alma.php**
* Allows library staff to run ```update_alma.py```. By default, interactive mode is off, so invoices that share an invoice number will be dropped.

## Common Issues ##
Library staff have reported the following common issues:
1. **Feed didn't generate**  
   Check the ```xml_to_apfeed``` log matching the most recent time. Since the script didn't complete, there will be no system link to latest_log. It is likely that an invoice record tripped a validation. Remove the offending record from the XML file, and have library finance try again. Remind library finance to reset the payment status of the invoice in Alma, and include in a future batch.
2. **Feed is wrong**  
   Library finance manually reviews the report generated from ```xml_to_apfeed``` to verify information was entered correctly into Alma. If an invoice is wrong, move the XML from the archive back to the original ```almadafis``` staging directory. Delete the apfeed that was previously generated. Selecting 'No' to the upload prompt on the apfeed webpage will do both of these tasks for you. Delete the offending invoice in the XML. Have finance generate the apfeed again, and remind to include invoice in future batch.

## TODO ##
* Phase 3
* Create an install gnu make target to install to a directory, currently it is just copied manually

## Attribution ##
* **Current Maintainer:** [Steve Pelkey](mailto:spelkey@ucdavis.edu)
* **Original Python Developer:** [Alexander Lin](mailto:alxlin@ucdavis.edu)
* **Original PHP Author:** [Michael Bavister](mailto:mdbavister@ucdavis.edu)
* **Project Owner:** [Dale Snapp](mailto:dfsnapp@ucdavis.edu)
* **Data analyst/mapping:** [Lisa Spagnolo](mailto:lcspagnolo@ucdavis.edu)

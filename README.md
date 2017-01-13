# README #

This application was commissioned by Dale Snapp, of the UC Davis Library IT.  Its purpose is to translate XML files from one server into Space-delimited text, then upload the resultant text file to the destination server.

The process makes a local working copy of the XML file in its "xml" folder, to ensure the original file remains unmolested.

### What is this repository for? ###

* Import an XML file from the Alma server
* Translate the data to a new space delimited text file.
* SCP Upload the resultant text file to the finance server.
* Developer: Alexander Lin
* Original Author: Michael Baxter
* version: 2.0

### Data and definitions ###

All sample data and data definitions are available in the BitBucket project's download area.

Files include:
* Excel file with Lisa's field mapping instructions.
* Sample XML data file from exlibris/repository
* Sample data output apfeed.LG file for modeling our output
* PDF with DaFISAPFeed File Layout instructions

### How do I get set up? ###

* Install the application files onto a server capable of running PHP from a command line.
* Configure xml_to_apfeed.php:
* Copy the entire folder, and all its files to a working directory on the server, which is accessible by PHP processor.
* Modify "./config.ini" to set the starting "org_doc_nbr" for your installation. This number will be used to track invoices processed by our process.
* Set the counter in './config.inc' to the beginning check number used for ORG_DOC_NBR (default = 30000001). 
* ORG_DOC_NBR must be exactly 7 digits long, even if it starts with zeroes (e.g. 0000001)
* Ensure the DEBUG constant is set to FALSE
* Check that the $local_folder points to the actual location of your inbound XML input folder for importing XML files.
* Verify that the server information used by $ftp_in & $ftp_out or $scp_out are valid.
* Dependencies:  N/A
* Database configuration:  N/A
* To run this application: 
* Place a properly formatted XML file on the server, in the folder configured as $local_folder.
* Run one of the three PHP files in the root application folder via browser or command line. - or - Configure a Cron job
*xml_to_apfeed.py:  The primary process responsible for translating XML files to Apfeed files and uploading them to the finance server.
*update_alma.py: (in development) The follow-up process responsible for reading the log files and trying to find matching records on the finance server. If checks have been cut, uses the Alma web APIs to update Alma records with the check info.
*apfeed_to_log:  A utility that should only need to be run if there are existing apfeed files in the "apfeed" folder and NO 'invoice.log' exists. Parses whatever files it finds in the "apfeed" folder and outputs the json_encoded array to create 'invoice.log'


### Logging: ###

Each time a script is run, it will generate an individual log file along with creating a symbolick link to the latest log (scriptname.latest.log)

### Testing ###
To run unit tests:
python2.7 -m unittest discover -s test

### Coverage ###
To run code coverage:
coverage run --omit "test/*" -m unittest discover -s
coverage report




### Who do I talk to? ###

* Repo owner or admin: Alexander Lin (alxlin@ucdavis.edu)
* Other community or team contact:
* Project owner Dale Snapp (dfsnapp@ucdavis.edu)
* Data analyst/mapping Lisa Spagnolo (lcspagnolo@ucdavis.edu)

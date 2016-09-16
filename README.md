# README #

This application was commissioned by Dale Snapp, of the UC Davis Library IT.  Its purpose is to translate XML files from one server into Space-delimited text, then upload the resultant text file to the destination server.

The process makes a local working copy of the XML file in its "xml" folder, to ensure the original file remains unmolested.

The apfeed output file is stored in the "apfeed" folder, and log files are stored in the "logs" folder.

### Update: 9/15/2016 ###

James reported an error with the apfeed header causing a file to be rejected.

* Updated the BATCH_ID_NBR function to use leading zeroes for all date/time values.

### Update: 8/31/2016 ###

Lisa sent a new XML input file and errors that had been generated.  The following updates were applied:

* Updated xml_to_apfeed.php to account for the variance in XML data found in the new input file.
	* All functions that received input values from the XML input file were adjusted to account for potentially missing data.
	* All items that relied on vendor_FinancialSys_Code were updated to use vendor_additional_code instead. This value appears consistently in both input files, and matches values sometimes found in vendor_FinancialSys_Code.
	* GOODS_RECEIVED_DT updated to use notList->note->owneredEntity when notelist is available. Otherwise, directly accessed owneredEntity (lines 481-485)

### Update: 8/9/2016 ###

This new version creates an additional log file "invoice.log" to track apfeed output content so we can use it to check with finance and find our records.  That, in turn, will allow us to update the Alma records when checks have been cut. 

### What is this repository for? ###

* Import an XML file from the Alma server
* Translate the data to a new space delimited text file.
* SCP Upload the resultant text file to the finance server.
* Programmer: Michael Baxter
* version: 1.2

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
    * Modify "./inc/config.inc" to set the starting "org_doc_nbr" for your installation. This number will be used to track invoices processed by our process.
    	* Set the counter in 'inc/config.inc' to the beginning check number used for ORG_DOC_NBR (default = 30000001). 
    	* ORG_DOC_NBR must be exactly 7 digits long, even if it starts with zeroes (e.g. 0000001)
    * Ensure the DEBUG constant is set to FALSE
    * Check that the $local_folder points to the actual location of your inbound XML input folder for importing XML files.
    * Verify that the server information used by $ftp_in & $ftp_out or $scp_out are valid.
* Dependencies:  N/A
* Database configuration:  N/A
* To run this application: 
    * Place a properly formatted XML file on the server, in the folder configured as $local_folder.
    * Run one of the three PHP files in the root application folder via browser or command line. - or - Configure a Cron job
    	*xml_to_apfeed.php:  The primary process responsible for translating XML files to Apfeed files and uploading them to the finance server.
    	*update_alma.php: (in development) The follow-up process responsible for reading the log files and trying to find matching records on the finance server. If checks have been cut, uses the Alma web APIs to update Alma records with the check info.
    	*apfeed_to_log:  A utility that should only need to be run if there are existing apfeed files in the "apfeed" folder and NO 'invoice.log' exists. Parses whatever files it finds in the "apfeed" folder and outputs the json_encoded array to create 'invoice.log'
    

### Logging: ###

All functions and errors are tracked in a session.log file, located in the logs folder.  Each run is time-stamped at the beginning and the end.

### Who do I talk to? ###

* Repo owner or admin:  Michael Baxter (michael@e2-photo.com)
* Other community or team contact: 
    * Project owner Dale Snapp (dfsnapp@ucdavis.edu)
    * Data analyst/mapping Lisa Spagnolo (lcspagnolo@ucdavis.edu)
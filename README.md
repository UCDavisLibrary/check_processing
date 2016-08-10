# README #

This application was commissioned by Dale Snapp, of the UC Davis Library IT.  Its purpose is to download XML files from one server, translate the data into Space-delimited text, then FTP upload the resultant text file to the destination server.

### What is this repository for? ###

* FTP Download a file from on UCD Library cloud server
* Translate the data to a new space delimited text file.
* Upload the resultant text file to the finance server.
* Programmer: Michael Baxter
* version: 0.5

### Data and definitions ###

All sample data and data definitions are available in the BitBucket project's download area.

Files include:
* Excel file with Lisa's field mapping instructions.
* Sample XML data file from exlibris/repository
* Sample data output apfeed.LG file for modeling our output
* PDF with DaFISAPFeed File Layout instructions

### How do I get set up? ###

* Install the application files onto a server capable of running PHP from a command line.
* Configure Index.php:
    * Set the $ftp_in and $ftp_out variables with the appropriate ftp information.
    * If your connections require SFTP, set the last variable in the appropriate $ftp->connect statement(s) to TRUE
    * Set the counter in 'inc/config.inc' to the beginning check number used for ORG_DOC_NBR (default = 30000001). It must be exactly 7 digits long, even if it starts with zeroes (e.g. 0000001)
* Dependencies:  N/A
* Database configuration:  N/A
* To run this application: 
    * Place a properly formatted XML file on the ftp_in server.
    * Run index.php via browser or command line. - or - Configure a Cron job

### Logging: ###

All functions and errors are tracked in a session.log file, located in the logs folder.  Each run is time-stamped at the beginning and the end.

### Who do I talk to? ###

* Repo owner or admin:  Michael Baxter (michael@e2-photo.com)
* Other community or team contact: 
    * Project owner Dale Snapp (dfsnapp@ucdavis.edu)
    * Data analyst/mapping Lisa Spagnolo (lcspagnolo@ucdavis.edu)
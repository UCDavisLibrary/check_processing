# README #

This application was commissioned by Dale Snapp, of the UC Davis Library IT.  Its purpose is to translate XML files from one server into Space-delimited text, then upload the resultant text file to the destination server.

The process makes a local working copy of the XML file in its "xml" folder, to ensure the original file remains unmolested.

### What is this repository for? ###

xml_to_apfeed.py
* Import an XML file from the Alma server
* Translate the data to a new space delimited text file.
* SCP Upload the resultant text file to the finance server.

update_alma.py
* Queries Alma for invoices waiting payments
* Queries KFS Oracle Database for invoices to see if they have been paid
* Creates an XML which will be updated to Alma to update invoices statuses

* Developer: Alexander Lin
* Original Author: Michael Baxter
* Version: 2.0

### How do I get set up? ###'
TODO:
Look Below


### Logging: ###
Each time a script is run, it will generate an individual log file along with creating a symbolick link to the latest log (scriptname.latest.log)

### MakeFile ###

Run Unit Tests
    make test

Run Coverage
    make coverage

Run pep8 style checking
    make pep8

### TODO ###
* Phase 3
* Create an install gnu make target to install to a directory, currently it is just copied manually
* pylint?


### Who do I talk to? ###

* Repo owner or admin: Alexander Lin (alxlin@ucdavis.edu)
* Other community or team contact:
* Project owner Dale Snapp (dfsnapp@ucdavis.edu)
* Data analyst/mapping Lisa Spagnolo (lcspagnolo@ucdavis.edu)

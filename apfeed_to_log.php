<?php
/*
 * Application:
 *                  Parse the apfeed files into a check log, to be used for updating Alma from finance
 * Author:
 *                  Michael Baxter
 * email:
 *                  michael@e2-photo.com
 * Last updated:
 *                  08/08/2016
 *
 */

// Set to TRUE for testing and debugging.
// affects some variable settings and error output.
defined('DEBUG') or define('DEBUG', FALSE);

date_default_timezone_set("America/Los_Angeles");

if (DEBUG===TRUE) echo "PHP version is " .phpversion();

$invoice_log_path   = './logs/invoice.log';
$apfeed_path        = './apfeed';

/*
* timeStamp()
*
* Purpose:
*      Provides a formatted current time stamp for inclusion
*      in the log file.
*  Input:
*      N/A
*  Output:
*      Formatted date/time string bracketed by [];
*/
function timeStamp(){
    return "\n".'['.date("m/d/Y g:i:s a",strtotime('now')).']';
}
/*
 *  parse_line()
 *
 * Purpose:
 *      Parses individual lines from the apfeed file into an array of the appropriate values
 *      using the parse formula provided in DaFISAPFeedFileLayout.pdf
 *  Input:
 *      $line = individual line (including end-of-line \n) as read from apfeed file.
 *  Output:
 *      Array of values parsed from the line.
 */
function parse_line($line){
    $out['FEED_NM'] = substr($line,0,15);
    $out['BATCH_ID_NBR'] = substr($line,15,14);
    $out['ORG_DOC_NBR'] = substr($line,29,7);
    $out['EMP_IND'] = substr($line,36,1);
    $out['VEND_NBR'] = substr($line,37,10);
    $out['VEND_ASSIGN_INV_NBR'] = substr($line,47,15);
    $out['VEND_ASSIGN_INV_DT'] = substr($line,62,8);
    $out['ADDR_SELECT_VEND_NBR'] = substr($line,70,10);
    $out['VEND_ADDR_TYP_CD'] = substr($line,80,4);
    $out['PMT_REMIT_NM'] = substr($line,84,40);
    $out['PMT_REMIT_LINE_1_ADDR'] = substr($line,124,40);
    $out['PMT_REMIT_LINE_2_ADDR'] = substr($line,164,40);
    $out['PMT_REMIT_LINE_3_ADDR'] = substr($line,204,40);
    $out['PMT_REMIT_CITY_NM'] = substr($line,244,40);
    $out['PMT_REMIT_ST_CD'] = substr($line,284,2);
    $out['PMT_REMIT_ZIP_CD'] = substr($line,286,11);
    $out['PMT_REMIT_CNTRY_CD'] = substr($line,297,2);
    $out['VEND_ST_RES_IND'] = substr($line,299,1);
    $out['INV_RECEIVED_DT'] = substr($line,300,8);
    $out['GOODS_RECEIVED_DT'] = substr($line,308,8);
    $out['ORG_SHP_ZIP_CD'] = substr($line,316,11);
    $out['ORG_SHP_STATE_CD'] = substr($line,327,2);
    $out['PMT_GRP_CD'] = substr($line,329,2);
    $out['INV_FOB_CD'] = substr($line,331,2);
    $out['DISC_TERM_CD'] = substr($line,333,2);
    $out['SCHEDULED_PMT_DT'] = substr($line,335,8);
    $out['PMT_NON_CHECK_IND'] = substr($line,343,1);
    $out['ATTACHMENT_REQ_IND'] = substr($line,344,1);
    $out['PMT_LINE_NBR'] = substr($line,345,5);
    $out['FIN_COA_CD'] = substr($line,350,2);
    $out['ACCOUNT_NBR'] = substr($line,352,7);
    $out['SUB_ATTC_NBR'] = substr($line,359,5);
    $out['FIN_OBJECT_CD'] = substr($line,364,4);
    $out['FIN_SUBJECT_OBJ_CD'] = substr($line,368,3);
    $out['PROJECT_CD'] = substr($line,371,10);
    $out['ORG_REFERENCE_ID'] = substr($line,381,8);
    $out['PMT_TAX_CD'] = substr($line,389,1);
    $out['PMT_AMT'] = substr($line,390,12);
    $out['APPLY_DISC_IND'] = substr($line,402,1);
    $out['EFT_OVERRIDE_IND'] = substr($line,403,1);
    $out['AP_PMT_PURPOSE_DESC'] = substr($line,404,1)=="\n" ? str_repeat(' ',120) : substr($line,404,120);
    $out['ALMA_UPDATED'] = FALSE;
    
    return $out;
}
/*
 *  get_invoice_items()
 *
 * Purpose:
 *      Reads line entries from the apfeed file and sends them to parse_line() 
 *      if they are of the proper file naming structure.
 *      Builds an array of the parsed output arrays.
 *  Input:
 *      $folder = The folder where the apfiles reside
 *      $filename = the filename of the current file in need of parsing.
 *  Output:
 *      Array of values parsed from the file $folder . '/' . $filename
 */
function get_invoice_items($folder,$filename){
    global $log;
    
    $out = array();
    
    if(file_exists($folder.'/'.$filename)){
        $toParse = fopen($folder.'/'.$filename,'r');
        while($line = fgets($toParse)){
            if (stristr($line, '*') === FALSE){
                $out[] = parse_line($line); 
            }
        }
        return $out;
        
    } else {
        fwrite($log,timeStamp().": File not found $folder/$filename");
        return FALSE;
    }
}

/*
 *  Main process
 *
 * Purpose:
 *      If this process has not been run (no checks.log file exists), reads all apfeed files from the
 *      apfeed folder into a check.log file, converting their line items to a json_encoded array for
 *      future processing by update_alma.php.      
 */

// open the log file for output from the last line
$log = fopen('./logs/session.log',"a+");

// record the beggining of each session.
$ts = str_ireplace("\n", "", timeStamp());

// if we already have a check.log, just record it and report it to the screen
if (file_exists($invoice_log_path)){
    // the next several lines convert the file contents to array
    // for the purposes of debugging/stepping through and examining the contents.
    $invoice_log = fopen($invoice_log_path,'r');
    $line = fgets($invoice_log);
    $arrVals = json_decode($line,TRUE);
//  foreach($arrVals as $key=>$objLineItem) $arrVals[$key] = (array)$objLineItem;
    
    // report the file's existence and exit.
    $msg = ">>$ts:  Invoice log already exists. Halting process conversion process. \n";
    fwrite($log, $msg);
    echo $msg;
} else {
    
    $arrInvoiceItems = array();
    
    // read the list of files from the apfeed folder
    $folder_contents = scandir($apfeed_path);
    
    // if a system php error was encountered, record it to the log file 
    if (isset($php_errormsg) && $php_errormsg !== '') fwrite($log, timeStamp().": {$php_errormsg}");
    
    // if we found files in the folder
    if ($folder_contents !== FALSE){
        
        // loop through all files in the folder
        foreach($folder_contents as $filename){
            
            // if the file is an apfeed file .. process it.
            if (is_file($apfeed_path.'/'.$filename) && strtolower($filename)!='.ds_store'){                
                fwrite($log, timeStamp().": checking $filename for invoices\n");
                
                // get the array of invoice items from the parser
                $arrLines = get_invoice_items($apfeed_path,$filename);
                
                // record our findings
                $count = $arrLines !== FALSE ? count($arrLines) : 0;
                fwrite($log, timeStamp().": read $count lines from $filename\n");
                
                // if we found line items, add them to the primary array
                if ($arrLines !== FALSE ){
                    if (empty($arrInvoiceItems)){
                        $arrInvoiceItems = $arrLines;
                    } else {
                        $arrInvoiceItems = array_merge($arrInvoiceItems,$arrLines);
                    } // end if arrInvoiceItems is empty
                } // end if arrLines has entries
            } // end if valid filename
        } // loop through each file in the folder
        
        // if the primary array has line items, record it to check.log
        if (!empty($arrInvoiceItems)){
            $invoice_log = fopen($invoice_log_path,'w');
            fwrite($invoice_log,json_encode($arrInvoiceItems));
            fclose($invoice_log);
            fwrite($log,timeStamp().": Created invoice log $invoice_log_path\n");
        }
    } // if the folder contains files
} // end if check log does not exist

fclose($log);

?>
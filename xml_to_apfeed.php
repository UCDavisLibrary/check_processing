<?php
/*
 * Application:
 *                  Import/Translate/Upload XML files to text files. Transfer those files to the target server via SCP for processing by Finance.
 *                  Log all activity in session.log.  Also store all output data in JSON format (invoice.log) for future processing by update_alma.php.
 * Author:
 *                  Michael Baxter
 * email: 
 *                  michael@e2-photo.com
 * Last updated:
 *                  08/31/2016
 *  -   All functions that received input values from the XML input file were adjusted to account for potentially missing data.
 *  -   All items that relied on vendor_FinancialSys_Code were updated to use vendor_additional_code instead. This value appears consistently in both input files, and matches values sometimes found in vendor_FinancialSys_Code.
 *  -   GOODS_RECEIVED_DT updated to use notList->note->owneredEntity when notelist is available. Otherwise, directly accessed owneredEntity (lines 481-485)
 *                  
 */

// Set DEBUT to TRUE for testing and debugging.
// affects some variable settings and error output.
defined('DEBUG') or define('DEBUG', FALSE);

date_default_timezone_set("America/Los_Angeles");

// default relative paths for key output files
$invoice_log_path     = './logs/invoice.log';
$apfeed_path        = './apfeed/';

if (DEBUG===TRUE) echo "PHP version is " .phpversion();

// change this if you need to use FTP instead
// Set the second parameter to "FTP" instead of "SCP"
define("SCP_OR_FTP", "SCP");

// check which upload process we're using and
// set the appropriate variables.
if (SCP_OR_FTP == "FTP") {
    require_once 'inc/class.ftp.php';
    $ftp_in = array(
        "server" => "<download_server_address>",
        "user" => "<ftp_username>",
        "pwd" => "<ftp_pwd>",
        "folder" => '/ucd/xml-in/'
    );
    
    $ftp_out = array(
        "server" => "<upload_server_address>",
        "user" => "<ftp_username>",
        "pwd" => "<ftp_pwd>",
        "folder" => '/ucd/txt-out/'
    );
} else {
        
    if (DEBUG===TRUE){
        $local_folder = 'home/almadafis/';
    } else {
        $local_folder = '/home/almadafis/';
    }
    $scp_out = array(
        "server" => "fis-depot.ucdavis.edu",
        "user" => "genlibap",
        "private_key" => "inc/OpenSSH_rsa_4096",
        "public_key" => "inc/OpenSSH_rsa_4096.pub",
        "folder" => ""
    );
}

/*
 *  Provides a formatted current time stamp for inclusion in the log file.
 *  
 *  @return string date/time string bracketed by [] for logging;
 */
function timeStamp(){
    return "\n".'['.date("m/d/Y g:i:s a",strtotime('now')).']';
}
/*
 * Field definitions taken from DaFISAPFeedFile.pdf
 */
function BATCH_ID_NBR(){
    return date('YmdHis',strtotime('now'));
}
function FEED_NM($name){
    $out = (isset($name) && trim($name)!=='' ? str_ireplace(' ','',strtoupper($name)) : ''). str_repeat(' ',15);
	return substr($out, 0,15);    	
}
function ORG_DOC_NBR($in){
    $out = (isset($in) && trim($in)!=='' ? trim($in) : '').str_repeat(' ',7);
    return substr($out,0,7);
}
function EMP_IND(){
    return 'N';
}
function VEND_NBR($vendor_code){
    $out = ( isset($vendor_code) && $vendor_code !== '' ? trim($vendor_code) : '' ) . str_repeat(' ',10);
    return substr($out,0,10);
}
function VEND_ASSIGN_INV_NBR($invoice_nbr){
    $out = ( isset($invoice_nbr) && trim($invoice_nbr)!=='' ? trim($invoice_nbr) : '') . str_repeat(' ',15);
    return substr($out,0,15);
}
function VEND_ASSIGN_INV_DT($invoice_dt){
    if (isset($invoice_dt) && trim($invoice_dt) !== ''){
        $arrDateParts = explode('/',$invoice_dt);
        $out = date('Ymd',strtotime($arrDateParts[2].'-'.$arrDateParts[0].'-'.$arrDateParts[1]) );
    } else {
        $out = str_repeat(' ', 8);
    }
    return $out;
}
function ADDR_SELECT_VEND_NBR($vendor_code){
    $out = ( isset($vendor_code) && trim($vendor_code) !== '' ? substr(trim($vendor_code),0,10) : '') . str_repeat(' ',10);
    return substr($out,0,10);
}
function VEND_ADDR_TYP_CD($vendor_code){
    $out =  ( isset($vendor_code) && trim($vendor_code) !== '' ? substr(trim($vendor_code),-4) : '') . str_repeat(' ',4);
    return substr($out,0,4);
}
function PMT_REMIT_NM(){
    return str_repeat(' ',40);
}
function PMT_REMIT_LINE_1_ADDR(){
    return str_repeat(' ',40);
}
function PMT_REMIT_LINE_2_ADDR(){
    return str_repeat(' ',40);
}
function PMT_REMIT_LINE_3_ADDR(){
    return str_repeat(' ',40);
}
function PMT_REMIT_CITY_NM(){
    return str_repeat(' ',40);
}
function PMT_REMIT_ST_CD(){
    return str_repeat(' ',2);
}
function PMT_REMIT_ZIP_CD(){
    return str_repeat(' ',11);
}
function PMT_REMIT_CNTRY_CD(){
    return str_repeat(' ',2);
}
function VEND_ST_RES_IND(){
    return str_repeat(' ',1);
}
function INV_RECEIVED_DT(){
    return str_repeat(' ',8);
}
function GOODS_RECEIVED_DT($creationDate){
    $out = (isset($creationDate) && trim($creationDate)!=='' ? trim($creationDate) : '').str_repeat(' ',8);
    return substr($out,0,8);
}
function ORG_SHP_ZIP_CD($zip){
    $out =  (isset($zip) && trim($zip)!=='' ? trim($zip) : ''). str_repeat(' ',11);
    return substr($out,0,11);
}
function ORG_SHP_STATE_CD($state){
    $out = (isset($state) && trim($state) !== '' ? trim($state) : ''). str_repeat(' ',2);
    return substr($out,0,2);
}
function PMT_GRP_CD(){
    return '2 ';
}
function INV_FOB_CD(){
    return str_repeat(' ',2);
}
function DISC_TERM_CD(){
    return str_repeat(' ',2);
}
function SCHEDULED_PMT_DT($dt_str){
    $out = (isset($dt_str) && trim($dt_str) !== '' ? substr($dt_str,0,8) : '') .str_repeat(' ',8);
    return substr($out,0,8);
}
function PMT_NON_CHECK_IND(){
    return 'N';
}
function ATTACHMENT_REQ_IND(){
    return 'N';
}
function PMT_LINE_NBR($line_number){
    $out = str_repeat('0',5) . (isset($line_number) && trim($line_number)!=='' ? trim($line_number) : '' );
    return substr($out,-5);
}
function FIN_COA_CD($cd){
    $out = (isset($cd) && trim($cd)!=='' ? trim($cd) : '') . str_repeat(' ',2);
    return substr($out,0,2);
}
function ACCOUNT_NBR($id){
    $out = ( isset($id) && trim($id)!=='' ? trim($id) : '' ) . str_repeat(' ',7);
    return substr($out,0,7);
}
function SUB_ACCT_NBR(){
    return str_repeat(' ',5);
}
function FIN_OBJECT_CD(){
    return '9200';
}
function FIN_SUB_OBJ_CD(){
    return str_repeat(' ',3);
}
function PROJECT_CD(){
    return str_repeat(' ',10);
}
function ORG_REFERENCE_ID($po_ln_num){
    $out = stristr($po_ln_num,'-',TRUE);
    if ($out === FALSE) {
        $out = trim($po_ln_num).str_repeat(' ', 8);
    } else {
        $out .='}'.str_repeat(' ',8);
    }
    
    return substr($out,0,8); 
}
function PMT_TAX_CD($vat_amt){
    if (isset($vat_amt) && trim($vat_amt)!==''){    
        $vat = floatval($vat_amt);
    } else {
        $vat = 0;
    }
    if ($vat > 0){
        return 'A';
    } else {
        return '0';
    }
}
/*
 * Formats PMT_AMT to 12 character spaces, including a leading "-" for negative numbers, and left-filled with zeroes
 * 
 * @param string ttl_price - parsed from XML to be converted to floating point.
 * 
 * @return string $out - a left-filled formatted string representation of ttl_price
 */
function PMT_AMT($ttl_price){
    $ttl = floatval(isset($ttl_price) && trim($ttl_price)!=='' ? $ttl_price : '0')*100;
    $out = sprintf("%'.012d",$ttl);
    return $out;
}
function APPLY_DISC_IND(){
    return 'N';
}
function EFT_OVERRIDE_IND(){
    return 'N';
}
function AP_PMT_PURPOSE_DESC($desc){
    $out = str_repeat(' ',120) . (isset($desc) && trim($desc)!== '' ? trim($desc) : '');
    return substr($out,0,120);
}
function RECORD_CT($records){
    $out = str_repeat('0',6) . (isset($records) && trim((string)$records)!=='' ? (string)$records : '');
    return substr($out,-6);    
}
/*
 *      Retrieves XML files from a local (local to this file) file
 *      system, and gathers path information into an array for further
 *      processing.
 *      
 *      If errors occur while copying files, the process
 *      continues after logging the errors directly.
 *      
 * @param string date dt_last_run
 *      Last modified date from the Log file, or 1 year ago (if
 *      the log file didn't already exist.
 * @return array file_paths
 *      Returns an array containing a list of filepaths for 
 *      XML files copies to this applications XML folder for 
 *      processing.
 *
 */
function local_get_xml($dt_last_run){
    global $log,$local_folder;

    try{

        $isDir = is_dir($local_folder);
        
        // get a file listing, including modified dates.
        $folder_contents = scandir($local_folder);
        
        if (isset($php_errormsg) && $php_errormsg !== '') $out['errors'] = timeStamp().": {$php_errormsg}"; 
        
        // if the folder contains files
        if ($folder_contents !== FALSE){
            $files = array();
            $arr_folders = explode('/',$local_folder);
            if (''==end($arr_folders)) array_pop($arr_folders);
            $folder = implode('/',$arr_folders);

            foreach($folder_contents as $name){ 
                if (!is_dir($name) && strtolower(substr($name, -4)) == '.xml' ) $files[] = $folder.'/'.$name;                    
            }
            if (!empty($files)){
                $dt_lr = date('Y-m-d g:i:s a',$dt_last_run);
    
                foreach($files as $file){
                    
                    $mod_date = filemtime($file);
        
                    // if the current file was created or modified
                    // after our log file was last modified, process
                    // get this file for processing
                    if ($mod_date > $dt_last_run){
                        $path_parts = explode('/',$file);
                        $filename = end($path_parts);
                        
                        $path_out = "xml/$filename";
                        fwrite($log, timeStamp().": Getting $filename for processing");
                        copy($file, $path_out);
                        $out['xml_files'][] = $path_out;
                    }
                } // loop foreach ftp file
            } // end if files found in folder
        } // end if something found in folder

        // return results
        return $out;

    } catch(Exception $e){
        $msg = timeStamp().": Error {$e->getCode()}: {$e->getMessage()} in line {$e->getLine()} of local_get_xml of {$e->getFile()}";
        if (DEBUG===TRUE) echo $msg;
        fwrite($log,$msg);
        return FALSE;
    }

}
/*
 *      Attempts to use FTP to retrieve XML files that have
 *      been posted since the last time this function ran.
 *      If found, downloads the files to the local XML folder
 *      and gathers path information into an array for further
 *      processing.
 * @param date dt_last_run
 *      Last modified date from the Log file, or 1 year ago (if
 *      the log file didn't already exist.
 * @return array of arrays
 *      Returns an array containing two arrays (1. FTP Errors, and
 *      2. List of filepaths for downloaded XML files).
 *      The recipient must examine the arrays to see which
 *      has been populated.
 *      It is NOT possible for both to contain errors.
 *      If errors occur while downloading files, the process
 *      continues after logging the errors directly.
 * 
 */
function ftp_get_xml($dt_last_run){
    global $log,$ftp_in;
    
    try{
        
        $ftp = new FTPClient();        
        $server = $ftp_in["server"];
        $user = $ftp_in["user"];
        $pwd = $ftp_in["pwd"];
        
        if ($ftp->connect($server,$user,$pwd,FALSE,FALSE)!==TRUE){
            // echo the logs. Might want to write
            // to an external log file at some point.
            $out['error'] = implode("\n\t",$ftp->get_messages());
            
        } else {
            // Switch to our working FTP folder
            $dir = $ftp_in['folder'];
            $continue = $ftp->cd($dir);
            
            if ($continue !== FALSE){
                // get a file listing, including modified dates.            
                $files = $ftp->list_files('.');
                $dt_lr = date('Y-m-d g:i:s a',$dt_last_run);
                
                foreach($files as $file){                              
                    $mod_date = is_int($file['modified']) ? $file['modified'] : strtotime($file['modified']);
                    
                    // if the current file was created or modified
                    // after our log file was last modified, process
                    // get this file for processing
                    if ($file['type'] == 'file' && $mod_date > $dt_last_run){
                        $filename = $file['name'];
                        $path_out = "xml/$filename";
                        fwrite($log, timeStamp().": Getting $filename from FTP server");
                        $ftp->download($filename, $path_out);
                        $out['xml_files'][] = $path_out;
                    }
                } // loop foreach ftp file
            } else {
                fwrite($log, timeStamp().": FTP directory not found ({$dir})");
            } // end if $continue
        } // end if ftp connected
        
        // close the FTP connection
        $ftp = NULL;
        // return results
        return $out;        
    
    } catch(Exception $e){
        $msg = timeStamp().": Error {$e->getCode()}: {$e->getMessage()} in line {$e->getLine()} of ftp_get_xml of {$e->getFile()}";        
        if (DEBUG===TRUE) echo $msg;
        fwrite($log,$msg);
        return FALSE;
    }

}
function get_apfeed_path(){
    global $apfeed_path;
    
    $filename = "apfeed.LG.".date('YmdGis',strtotime('now'));
    $apfeed = $apfeed_path . $filename;
    
    return $apfeed;
}
function get_invoice_info($invoice_log){
    $log_info = array();
    
    while ($line = fgets($invoice_log)){
        if ($line !== '\n' && $line !== ''){
            if (empty($log_info)){
                $log_info = json_decode($line,TRUE);                
            } else {
                $log_info = array_merge($log_info, json_decode($line,TRUE));
            } // end if log info empty
        } // end if line not eol / eof
    } // loop while
    
    return $log_info;
}
/*
 * export_to_apfeed()
 * 
 * Purpose:
 *      Imports and parses downloaded XML files,
 *      then exports them to "apfeed" files in a separate
 *      apfeed folder.
 * Input:
 *      Array of filepaths to downloaded XML files.
 * Output:
 *      Array of exported text files for uploading
 *      to the FTP server.
 */
function export_to_apfeed($xml_files){
    global $log,$ini,$invoice_info;
    
    try{
        $apfeed_file_out = array();
        foreach($xml_files as $xml_file_in){
            $xml = simplexml_load_file($xml_file_in);
            
            if ($xml === FALSE){
                fwrite($log,timeStamp().": Failed to parse $xml_file_in");
            } else{
                $arrFilenameParts = explode('/',$xml_file_in);              
                $apfeed = get_apfeed_path();
                // ensure we have a unique file, and do not overwrite an existing one.
                while(file_exists($apfeed)){
                    sleep(1);
                    $apfeed = get_apfeed_path();
                }
                $apfeed_file = fopen($apfeed,"w");
        
                // test the waters by writing the header line
                $header_fields = array("HEADER_ID"=>'**HEADER',"FEED_ID"=>'LG',"FEED_NM"=>FEED_NM('GENERALLIBRARY'),"BATCH_ID_NBR"=>BATCH_ID_NBR());                
                $success = fwrite($apfeed_file, implode('',$header_fields)."\n" );
                
                if ($success === FALSE){
                    fwrite($log,timeStamp().": Failed to export apfeed file: $apfeed_file");
                } else {      
                    
                    $record_ct = 0;
                    
                    foreach($xml as $invoice_list){
                        foreach($invoice_list as $invoice){
                            $ini->org_doc_nbr += 1;
                            foreach($invoice->invoice_line_list as $line_list){
                                foreach($line_list as $line){
                                    // mvb - add object variables to enable writing out to the 
                                    // checks.log file via json_encode arrays.
                                    $inv_item['FEED_NM']             =  $header_fields['FEED_NM'];
                                    $inv_item['BATCH_ID_NBR']        =  $header_fields['BATCH_ID_NBR'];
                                    $inv_item['ORG_DOC_NBR']         =  ORG_DOC_NBR((string)$ini->org_doc_nbr);
                                    $inv_item['EMP_IND']             =  EMP_IND();
                                    $inv_item['VEND_NBR']            =  VEND_NBR($invoice->vendor_additional_code);
                                    $inv_item['VEND_ASSIGN_INV_NBR']     = VEND_ASSIGN_INV_NBR($invoice->invoice_number);
                                    $inv_item['VEND_ASSIGN_INV_DT']      = VEND_ASSIGN_INV_DT($invoice->invoice_date);
                                    $inv_item['ADDR_SELECT_VEND_NBR']    = ADDR_SELECT_VEND_NBR($invoice->vendor_additional_code);
                                    $inv_item['VEND_ADDR_TYP_CD']        = VEND_ADDR_TYP_CD($invoice->vendor_additional_code);
                                    $inv_item['PMT_REMIT_NM']            = PMT_REMIT_NM();
                                    $inv_item['PMT_REMIT_LINE_1_ADDR']   = PMT_REMIT_LINE_1_ADDR();
                                    $inv_item['PMT_REMIT_LINE_2_ADDR']   = PMT_REMIT_LINE_2_ADDR();
                                    $inv_item['PMT_REMIT_LINE_3_ADDR']   = PMT_REMIT_LINE_3_ADDR();
                                    $inv_item['PMT_REMIT_CITY_NM']       = PMT_REMIT_CITY_NM();
                                    $inv_item['PMT_REMIT_ST_CD']         = PMT_REMIT_ST_CD();
                                    $inv_item['PMT_REMIT_ZIP_CD']        = PMT_REMIT_ZIP_CD();
                                    $inv_item['PMT_REMIT_CNTRY_CD']      = PMT_REMIT_CNTRY_CD();
                                    $inv_item['VEND_ST_RES_IND']         = VEND_ST_RES_IND();
                                    $inv_item['INV_RECEIVED_DT']         = INV_RECEIVED_DT();
                                    if (property_exists($invoice, 'noteList')){
                                        $inv_item['GOODS_RECEIVED_DT']       = GOODS_RECEIVED_DT($invoice->noteList->note->owneredEntity->creationDate);
                                    }else{
                                        $inv_item['GOODS_RECEIVED_DT']       = GOODS_RECEIVED_DT($invoice->owneredEntity->creationDate);
                                    }
                                    $inv_item['ORG_SHP_ZIP_CD']          = ORG_SHP_ZIP_CD('95616-5292');
                                    $inv_item['ORG_SHP_STATE_CD']        = ORG_SHP_STATE_CD('CA');
                                    $inv_item['PMT_GRP_CD']              = PMT_GRP_CD();
                                    $inv_item['INV_FOB_CD']              = INV_FOB_CD();
                                    $inv_item['DISC_TERM_CD']            = DISC_TERM_CD();
                                    $inv_item['SCHEDULED_PMT_DT']        = SCHEDULED_PMT_DT($header_fields['BATCH_ID_NBR']);
                                    $inv_item['PMT_NON_CHECK_IND']       = PMT_NON_CHECK_IND();
                                    $inv_item['ATTACHMENT_REQ_IND']      = ATTACHMENT_REQ_IND();                            
                                    $inv_item['PMT_LINE_NBR']            = PMT_LINE_NBR($line->line_number);
                                    $inv_item['FIN_COA_CD']              = FIN_COA_CD('3');
                                    $inv_item['ACCOUNT_NBR']             = ACCOUNT_NBR($line->fund_info_list->fund_info->external_id);
                                    $inv_item['SUB_ACCT_NBR']            = SUB_ACCT_NBR();
                                    $inv_item['FIN_OBJECT_CD']           = FIN_OBJECT_CD();
                                    $inv_item['FIN_SUB_OBJ_CD']          = FIN_SUB_OBJ_CD();
                                    $inv_item['PROJECT_CD']              = PROJECT_CD();
                                    $inv_item['ORG_REFERENCE_ID']        = ORG_REFERENCE_ID($line->po_line_info->po_line_number);
                                    $inv_item['PMT_TAX_CD']              = PMT_TAX_CD($invoice->vat_info->vat_amount);
                                    $inv_item['PMT_AMT']                 = PMT_AMT($line->fund_info_list->fund_info->amount->sum);
                                    $inv_item['APPLY_DISC_IND']          = APPLY_DISC_IND();
                                    $inv_item['EFT_OVERRIDE_IND']        = EFT_OVERRIDE_IND();
                                    $inv_item['AP_PMT_PURPOSE_DESC']     = AP_PMT_PURPOSE_DESC('');
                                    
                                    $entry = implode('',$inv_item)."\n";
                                    $inv_item['ALMA_UPDATED']           = FALSE;
                                                                                                    
                                    $success = fwrite($apfeed_file,$entry);
                                    if ($success !== FALSE) {
                                        $record_ct += 1;
                                        $line_id = $inv_item['VEND_ASSIGN_INV_NBR']."~".$inv_item["PMT_LINE_NBR"];
                                        if (!array_key_exists($line_id, $invoice_info)) $invoice_info[$line_id] = $inv_item;
                                    }
                                } // loop each line
                            } // loop each line list
                        } // loop each invoice
                    }   // loop each invoice list
                    $trailer_fields = array("TRAILER_ID"=>'**TRAILER',"FEED_NM"=>$header_fields['FEED_NM'],"RECORD_COUNT"=>RECORD_CT($record_ct) );
                    fwrite($apfeed_file,implode('',$trailer_fields)."\n");
                    fwrite($log,timeStamp().": Recorded $record_ct lines to export file $apfeed");
                    
                    fclose($apfeed_file);
                    
                    $apfeed_file_out[] = $apfeed;
                    // update the ini to increment ORG_DOC_NBR
                    update_ini();
                    
                } // end if wrote headers
            } // end if xml parsed    
        } // loop foreach
        return empty($apfeed_file_out) ? FALSE : $apfeed_file_out;
    } catch(Exception $e){
        $msg = timeStamp().": Error {$e->getCode()}: {$e->getMessage()} in line {$e->getLine()} of export_to_apfeed of {$e->getFile()}";
        if (DEBUG===TRUE) echo $msg;
        fwrite($log,$msg);
        return FALSE;        
    }
}
/*
 * scp_upload_apfeed_files()
 *
 * Purpose:
 *      Upload converted files to the appropriate FTP
 *      location for consumption by other processes.
 * Input:
 *      Array of text files that were output by the
 *      XML to APFEED conversion process.
 * Output:
 *      Array of arrays listing Errors or Successfully uploaded file names.
 */
function scp_upload_apfeed_files($files){
    global $log,$scp_out;

    try{        
        $server = $scp_out["server"];
        $user = $scp_out["user"];
        $pub_key = $scp_out["public_key"];
        $private_key = $scp_out['private_key'];
        $folder = $scp_out['folder'] == '' ? './' : $scp_out['folder'];
        
       
        $out = array('error'=>array(),'apfeed_files'=>array());

    
        foreach($files as $filepath){                
            $path_parts = explode('/',$filepath);
            
            // just using filename because the SCP does not require an explicit folder
            $filename = end($path_parts);
            
            fwrite($log,timeStamp().": Uploading $filename to $server");
            
            if (is_array($output)) unset($output);
            
            $success = system("scp -i $private_key $filepath {$user}@{$server}:",$shell_msg);
            
            $status = $success===FALSE ? 'error' : 'result';
            
            fwrite($log,timeStamp().": Upload {$status}: {$shell_msg}".($success!=='' && $success!==FALSE ? " :: {$success}" : "") );
            
            $out['apfeed_files'][] = $filepath;
        } // loop foreach ftp file
            
        // return results
        return $out;

    } catch(Exception $e){
        $msg = timeStamp().": Error {$e->getCode()}: {$e->getMessage()} in line {$e->getLine()} of scp_upload_apfeed_files of {$e->getFile()}";
        if (DEBUG===TRUE) echo $msg;
        fwrite($log,$msg);
        return FALSE;
    }

}
/*
 * ftp_upload_apfeed_files()
 * 
 * Purpose:
 *      Upload converted files to the appropriate FTP
 *      location for consumption by other processes.
 * Input:
 *      Array of text files that were output by the
 *      XML to APFEED conversion process.
 * Output:
 *      Array of arrays listing Errors or Successfully uploaded file names.
 */
function ftp_upload_apfeed_files($files){
    global $log,$ftp_out;
    
    try{
        $ftp = new FTPClient();
        $out = array('error'=>array(),'apfeed_files'=>array());
        
        $server = $ftp_out["server"];
        $user = $ftp_out["user"];
        $pwd = $ftp_out["pwd"];
        
        if ($ftp->connect($server,$user,$pwd,FALSE,FALSE)!==TRUE){
            // echo the logs. Might want to write
            // to an external log file at some point.
            return $out['error'] = implode("\n\t",$ftp->get_messages());
            
        } else {
            // Switch to our working FTP folder            
            $dir = $ftp_out['folder'];
            $continue = $ftp->cd($dir);
            
            if ($continue){                
                foreach($files as $filepath){
                    $path_parts = explode('/',$filepath);
                    $filename = end($path_parts);
                    $uploaded = $ftp->upload($filepath, $filename);
                    if ($uploaded===FALSE) {
                        fwrite($log,timeStamp().": Failed to upload $filename");
                    } else {
                        fwrite($log,timeStamp().": Uploaded $filename to $server");
                        $out['apfeed_files'][] = $filepath;
                    }                 
                } // loop foreach ftp file
            } else {
                $out['error'][] = "Directory not found ({$dir})";
            }
        } // end if ftp connected
        
        // close the FTP connection
        $ftp = NULL;
        // return results
        return $out;
    
    } catch(Exception $e){
        $msg = timeStamp().": Error {$e->getCode()}: {$e->getMessage()} in line {$e->getLine()} of ftp_upload_apfeed_files of {$e->getFile()}";
        if (DEBUG===TRUE) echo $msg;
        fwrite($log,$msg);
        return FALSE;
    }

}
/*
 * delete_files()
 * 
 * Purpose:
 *      remove working files so they don't get processed
 *      multiple times
 * Input:
 *      array of files to be deleted.
 * Output:
 *      arrays of files that failed and/or succeeded in
 *      being deleted.
 *      
 */
function delete_files($files){
    global $log;
    try{
        if (is_array($files) && !empty($files)){
            $bad = array();
            $good = array();
            foreach($files as $filepath){
                $success = unlink($filepath);
                if ($success === FALSE){
                    $bad[] = $filepath;
                } else {
                    $good[] = $filepath;
                }
            }
            return array("deleted"=>$good,"failed"=>$bad);
        }
    } catch(Exception $e){
        $msg = timeStamp().": Error {$e->getCode()}: {$e->getMessage()} in line {$e->getLine()} of ftp_upload_apfeed_files of {$e->getFile()}";
        if (DEBUG===TRUE) echo $msg;
        fwrite($log,$msg);
        return FALSE;
    }
}
/*
 * update_ini()
 *
 * Purpose:
 *      writes the latest settings back to our
 *      "INI" files (config.inc), so we can use it
 *      again next run.
 * Input:
 *      N/A
 * Output:
 *      N/A
 *
 */
function update_ini(){
    global $ini;
    
    file_put_contents('inc/config.inc',json_encode($ini) );
}
//*********  Main process   ************************//
/*
 *  -Gets or creates a new session log.
 *  -If a new log needs to be created, uses
 *  one year ago as comparison date for new
 *  XML files found on the FTP server.
 *  -If existing session log is found, uses
 *  last modified date of session log for comparison
 *  date.
 *  -Imports XML files from FTP server, into XML folder.
 *  -Consumes and converts those XML files,
 *  outputting the results to text files in the apfeed folder.
 *  -Finally, uploads the text files to their target
 *  FTP server.
 *  
 *  Files are deleted following each stage.
 *  
 ***************************************************/

// if the log exists use its mod date for comparisons
if (file_exists('logs/session.log')){
    // get stats from the existing log
    // $file_info = stat('logs/session.log');     
    // $dt_last_run = $file_info['mtime'];
    $dt_last_run = filemtime('logs/session.log');
    if (DEBUG === TRUE) $dt_last_run = strtotime("-1 year");
    
    // start a new log if we're greater than or equal to 5MB
    if (filesize('logs/session.log') >= 5242880) {
        $ts = date('mdY',strtotime('now'));
        rename('session.log',"session$ts".'.log');    
    }
} else {        
    // default to one year ago (for now)
    $dt_last_run = strtotime("-1 year");
}

// open the log file for output from the last line
$log = fopen('./logs/session.log',"a+");

// record the beggining of each session.
$ts = str_ireplace("\n", "", timeStamp());
fwrite($log, "//***                    $ts BEGIN SESSION                    ***//\n");

// try to retrieve XML files from the FTP server
$xml_results = SCP_OR_FTP == "FTP" ? ftp_get_xml($dt_last_run) : local_get_xml($dt_last_run);

// if FTP error occured, log it. Otherwise proceeed
if (!empty($xml_results['error'])){
    fwrite($log, timeStamp().": FTP Errors occurred\n\t".$xml_results['error']);
} else {
        
    // if the list is not empty, process them
    if (isset($xml_results['xml_files']) && !empty($xml_results['xml_files'])){
        
        // get the list of successfully downloaded xml files
        $xml_files = $xml_results['xml_files'];

        $ini = json_decode(file_get_contents('inc/config.inc',TRUE));
        
        // open the invoice log and read its contents int an array.
        if (file_exists($invoice_log_path)){
            $invoice_log = fopen($invoice_log_path,'r+');        
            $invoice_info = get_invoice_info($invoice_log);            
            fclose($invoice_log);
        } else {
            $invoice_info = array();
        }
                
                
        // try to convert XML files to APFEED
        $apfeed_exported = export_to_apfeed($xml_files);
        
        // if the export failed, log errors.  Otherwise, proceed to upload them.
        if ($apfeed_exported === FALSE){
            fwrite($log,timeStamp().": Failed to export one or more apfeed files");
        } else {
            
            // re-open the log, but clear it and prep to write contents from scratch
            $invoice_log = fopen($invoice_log_path,'w');
            fwrite($invoice_log,json_encode($invoice_info)."\n");
            
            // log what we processed and record completion time.
            $file_ct = count($apfeed_exported);
            fwrite($log,timeStamp().": Finished translatting $file_ct XML file(s) to apfeed.");
            
            // try to upload the apfeed files to the ftp server
            $upload_results = SCP_OR_FTP == 'FTP' ? ftp_upload_apfeed_files($apfeed_exported) : scp_upload_apfeed_files($apfeed_exported);
            
            // if ftp errors occurred, record them. Otherwise, log upload stats.
            if (!empty($upload_results['error'])){
                fwrite($log, timeStamp().": FTP Errors occurred\n\t".$upload_results['error']);
            } else {
                $upload_ct = count($upload_results['apfeed_files']);
                fwrite($log,timeStamp().": Finished uploading $upload_ct apfeed file(s).");
            } // end if ftp errors found in apfeed upload process
            
            //mvb - Disable apfeed deletion for now, so we can see if they're being created.
//          delete_files($apfeed_exported);            
        }
        
//        delete_files($xml_files);
        
    } else {
        fwrite($log,timeStamp().": No XML files to process");
    }
 }
fwrite($log, "\n\n//***                     $ts END SESSION                     ***//\n\n");
fclose($log);

?>

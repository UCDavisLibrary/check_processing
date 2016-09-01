<?php
/*
 * Application:
 *                  Read the list of invoices to research from invoice.log. Try to find
 *                  the file info in the finance database using KFS Query. If found, update Alma via
 *                  web api, to indicate process status (require php_curl).
 * Author:
 *                  Michael Baxter
 * email:
 *                  michael@e2-photo.com
 * Last updated:
 *                  08/09/2016
 *
 */
use PDOOCI\PDO;
require_once 'inc/class.PDOOCI.php';

// relative path locations for key input/output logs
$invoice_log_path   = './logs/invoice.log';
$apfeed_path        = './apfeed';
$alma_api_key       = 'l7xx768e97ddd72b4177a913f6b804041661';

/*
 *  Provides a formatted current time stamp for inclusion
 *  in the log file.
 *  
 *  @return Formatted date/time string bracketed by [];
 */
function timeStamp(){
    return "\n".'['.date("m/d/Y g:i:s a",strtotime('now')).']';
}
/*
 *  Callback for usort, to sort invoice info by key field
 *      
 *  @param $a Array value for comparison against $b
 *  @param $b Array value for comparison against $a
 *  
 *  @return sorted array values;
 *  
 */
function comp($a, $b){
    return strcmp($a['BATCH_ID_NBR'], $b['BATCH_ID_NBR']);
}
/*
 *  Parse the passed json_decode objects into array items in the primary processing array.
 *  
 *  @param $arrInvoices (By reference) primary processing array being built
 *  @param $arrLine     json_decoded array of objects, parsed from a line of invoice.log
 *  
 *  @return  N/A ... $arrInvoices is passed by reference so it can be directly modified without
 *              the need to pass anything back;
 */
function add_items(&$arrInvoices,$arrLine){
    foreach($arrLine as $key=>$objInvoices) $arrInvoices[] = (array) $objInvoices;
}
/*
 *  Try to find matching Alma record(s) via the Web APIs provided
 *  at https://developers.exlibrisgroup.com/alma
 *  
 *  @param $row_data Array of invoices and their respective fields
 *  
 *  @return boolean success to indicate if a matching record was found
 */
function get_alma_po_line($invoice_number){
    global $alma_api_key;
    
    //API Url
    $url = "https://api-na.hosted.exlibrisgroup.com/almaws/v1/acq/invoices?apikey={$alma_api_key}&format=json&q=invoice_number~$invoice_number";
    
    //  Initiate curl
    $ch = curl_init();
    
    // Disable SSL verification
    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    
    // Will return the response, if false it print the response
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    
    // Set the url
    curl_setopt($ch, CURLOPT_URL,$url);
    
    //Set the content type to application/json
    curl_setopt($ch, CURLOPT_HTTPHEADER, array('Accept: application/json'));
    
    // Execute
    $result=curl_exec($ch);
    
    // Closing
    curl_close($ch);
    
    $arrDecoded = json_decode($result,TRUE);
    
    $arrInvoice = (is_array($arrDecoded) && array_key_exists('invoice', $arrDecoded) ? $arrDecoded['invoice'] : NULL);
        
    if (is_array($arrInvoice) && !empty($arrInvoice)){
        $invoice_line = $arrInvoice[0]['invoice_line'][0];
        $po_line = array_key_exists('po_line', $invoice_line) ? $invoice_line['po_line'] : FALSE;        
        return $link == '' ? FALSE : $link;
    }else{
        return FALSE;
    }
}
/*
 *  Push update information to Alma via the Web APIs provided
 *  at https://developers.exlibrisgroup.com/alma
 *
 *  @param $row_data Array of invoices and their respective fields
 *
 *  @return boolean $success to indicate if we updated properly
 */
function update_alma_record($row_data){
    global $alma_api_key;
    
    // get the alma record to ensure we have something to update
    $po_line = get_alma_po_line($row_data['VENDOR_INVOICE_NUM']);
    
    if ($po_line !== FALSE){
        
        //API Url
        $url = $url = "https://api-na.hosted.exlibrisgroup.com/almaws/v1/acq/po-lines/{$po_line}?apikey={$alma_api_key}&format=json";
        
        //Initiate cURL.
        $ch = curl_init($url);

        
        /*
         *  Payment_status would be updated from “NOT_PAID” to “PAID”
         *  voucher_number would come from KFS field "CHECK_NUM"
         *  voucher_date => … "PAYMENT_ENTERED_DATE"
         *  voucher_amount => … "PAYMENT_TOTAL_AMT"
         */
        $updates = array(
            "payment_status"=>'PAID',
            "voucher_number"=>'C10457745',
            "voucher_date"=>'20160719',
            "voucher_amount"=>24.14            
        );
                    
        
        //Encode the array into JSON. 
        //(mvb ... we probably want a subset of the data, and we need the API Key)
        $jsonDataEncoded = json_encode($updates);
        
        //Tell cURL that we want to send a PUT request.
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "PUT");
        
        //Attach our encoded JSON string to the POST fields.
        curl_setopt($ch, CURLOPT_POSTFIELDS, $jsonDataEncoded);
        
        //Set the content type to application/json
        curl_setopt($ch, CURLOPT_HTTPHEADER, array('Content-Type: application/json'));
        
        // for testing ... to prevent accidentally updating something
        return TRUE;
        //Execute the request
        //$result = curl_exec($ch);
                
    } else {
        return FALSE;
    }
}
/*
 *  Main process
 *
 * Purpose:
 *      If this process has not been run (no invoice.log file exists), reads all apfeed files from the
 *      apfeed folder into a invoice.log file, converting their line items to a json_encoded array for
 *      future processing by update_alma.php.
 */

// open the log file for output from the last line
$log = fopen('./logs/session.log','a+');

// record the beggining of each session.
$ts = str_ireplace("\n", "", timeStamp());

// if we already have a invoice.log, just record it and report it to the screen
if (file_exists($invoice_log_path)){
    $invoice_log = fopen($invoice_log_path,"r");
    while ($line = fgets($invoice_log)){
        add_items($arrInvoices,json_decode($line,true));        
    }    
    
    if (!empty($arrInvoices)){
        // sort the invoices by batch id for faster processing
        usort($arrInvoices,"comp");
        
        // initialize the connection to the finance server, so we can look for status update info.
        $db_dafis = "(
                DESCRIPTION=(
                    ADDRESS_LIST=(
                        ADDRESS=(COMMUNITY=TCP.ucdavis.edu)
                                (PROTOCOL=TCP)
                                (Host=AFS-ODADEV1.ucdavis.edu)
                                (Port=1521)
                                )
                           )
                (
                 CONNECT_DATA=(SID=dsstage)
                              (GLOBAL_NAME=fis_ds_stage.ucdavis.edu)
                 )
           )";
        $db_user_dafis = 'ucdlibrary_app';
        $db_pass_dafis = 'Pan$8562#ama';
        
        $dafis_dbh = new PDOOCI\PDO( $db_dafis, $db_user_dafis, $db_pass_dafis);
        
        // Query the finance server to find the current status of each invoice
        $kfs_query = <<<EOT
                    select * from (
                        select DV.fdoc_nbr                              AS doc_num
                            , PD.dv_payee_id_nbr                        AS vendor_id
                            , PD.dv_payee_prsn_nm                       AS vendor_name
                            , NVL(PPD.inv_nbr, 'MISSING INV#')          AS vendor_invoice_num
                            , NVL(DV.dv_chk_nbr, ' ')                   AS check_num
                            , DV.dv_chk_tot_amt                         AS payment_total_amt
                            , to_char(DV.dv_pd_dt, 'YYYYMMDD')          AS payment_entered_date
                            , DT.doc_typ_nm                             AS doc_type
                          from finance.fp_dv_doc_t DV
                            join finance.fp_dv_payee_dtl_t PD
                              on PD.fdoc_nbr = DV.fdoc_nbr
                            join finance.rice_krew_doc_hdr_ext_t DHX
                              on DHX.doc_hdr_id = DV.fdoc_nbr
                            join finance.rice_krew_doc_hdr_t DH
                              on DH.doc_hdr_id = DV.fdoc_nbr
                            join finance.rice_krew_doc_typ_t DT
                              on DT.doc_typ_id = DH.doc_typ_id
                            join finance.pdp_pmt_dtl_t PPD
                              on ppd.cust_pmt_doc_nbr = DV.fdoc_nbr
                          where DHX.val in
                              ( 'ULBK'
                              , 'BKDE'
                              , 'BKDG'
                              , 'BKFE'
                              , 'BKRE'                                     
                              )
                        UNION
                        select CM.fdoc_nbr                         AS doc_num
                            , CM.vndr_cust_nbr                     AS vendor_id
                            , CM.vndr_nm                           AS vendor_name
                            , CM.crdt_memo_nbr                     AS vendor_invoice_num
                            , nvl(CM.pmt_disb_nbr, ' ')            AS check_num
                            , CM.crdt_memo_amt                     AS payment_total_amt
                            , to_char(CM.ap_aprvl_dt, 'YYYYMMDD')  AS payment_entered_date
                            , DT.doc_typ_nm                        AS doc_type
                          from finance.ap_crdt_memo_t CM
                            join finance.rice_krew_doc_hdr_t DH
                              on DH.doc_hdr_id = CM.fdoc_nbr
                            join finance.rice_krew_doc_typ_t DT
                              on DT.doc_typ_id = DH.doc_typ_id
                          where cm_feed_cd = 'LG'
                        )
                      where vendor_id like '%'||:vend_id||'%'  
                      and vendor_invoice_num = :inv_nbr
                      order by doc_num
EOT;
        $statement = $dafis_dbh->prepare($kfs_query);
        
        $dump_file = fopen('./logs/dump.log','w');
        
        $last_invoice = '';
        
        
        // loop through invoice data using vendor_id and vendor_invoice_num to invoice on status
        foreach($arrInvoices as $invoice){
            if ($invoice['VEND_ASSIGN_INV_NBR'] !== $last_invoice){
                $last_invoice = $invoice['VEND_ASSIGN_INV_NBR'];
                
                $inv_nbr = $invoice['VEND_ASSIGN_INV_NBR']*1;
                $vend_id = (string)$invoice['VEND_NBR']*1;
                $statement->execute( array(':inv_nbr' => $inv_nbr,':vend_id'=>$vend_id) );            
                
                // loop through result rows updating alma via the Web APIs
                while ($row = $statement->fetch()){
                    //update Alma via Web API
                    $updated_alma = update_alma_record((array)$row);
                    fwrite($dump_file,json_encode($row));
                    
                    // go ahead and break. We only need to update once 
                    break;
                }
            } else {
                $invoice['ALMA_UPDATED']=$updated_alma;
            }
        }
        
        fclose($dump_file);
        
        
        
        // if finance info is available, update alma via the Web API
    }
    
}
?>
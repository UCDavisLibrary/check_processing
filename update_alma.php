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
$invoice_xml_path   = './xml/';
$apfeed_path        = './apfeed';
$alma_api_key       = 'l7xx768e97ddd72b4177a913f6b804041661';

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
 * Converts vendor_additional_code from XML to the dafis vendor_id
 * vendor_additional_code example: 0000008563 0005
 * the expected vendor_id: 8563-0 
 */
function vend_addcode_to_dafis($vend_code) {
    list($first, $sec) = preg_split('/\s+/', $vend_code);
    $first = preg_replace("/^0+/",'', $first);
    $sec = $sec[1];
    return "$first-$sec";
}

/*
 * Converts MM-DD-YYYY to YYYYMMDD
 */
function sdate_ymd($date) { 
    list($mon,$day,$year) = explode("/", $date);
    return "$year$mon$day";   
}
/*
 * Uses CURL to access alma REST api
 * https://developers.exlibrisgroup.com/alma/apis/acq/GET/gwPcGly021r2HStoodvfjbXCmeKQd8Gt3JPdiJpJhUA=/d5b14609-b590-470e-baba-9944682f8c7e
 */ 

function query_alma_invoice($offset = 0) {
    $ch = curl_init();
    $url = 'https://api-eu.hosted.exlibrisgroup.com/almaws/v1/acq/invoices/';
    $queryParams = '?' . urlencode('q') . '=' . urlencode('status~ready_to_be_paid') 
        . '&' . urlencode('apikey') . '=' . urlencode('l7xx768e97ddd72b4177a913f6b804041661')
        . '&' . urlencode('format') . '='. urlencode('json')
        . '&' . urlencode('limit') . '=' . urlencode('100')
        . '&' . urlencode('offset') . '=' . urlencode($offset); 
    curl_setopt($ch, CURLOPT_URL, $url . $queryParams);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, TRUE);
    curl_setopt($ch, CURLOPT_HEADER, FALSE);
    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'GET');
    $response = curl_exec($ch);
    curl_close($ch);

    return($response);
}
/* 
 * Grabs all waiting for payment invoices from alma
 * Done in parallel using curl multi
 * Can't be done using one curlc call because of alma 100 invoice limitations
 * Returns an array
 */

function get_waiting_invoices() {
    // Gets the initial query to get total number of invoices
    $respond_json = json_decode(query_alma_invoice());
    $array_out = $respond_json->invoice;

    // creates each seperation for parallel 
    $nodes = range(100, $respond_json->total_record_count, 100);
    $node_count = count($nodes);

    $curl_arr = array();
    $master = curl_multi_init();

    for($i = 0; $i < $node_count; $i++)
    {
        $url = 'https://api-eu.hosted.exlibrisgroup.com/almaws/v1/acq/invoices/?' . urlencode('q') . '=' . urlencode('status~ready_to_be_paid') 
        . '&' . urlencode('apikey') . '=' . urlencode('l7xx768e97ddd72b4177a913f6b804041661')
        . '&' . urlencode('format') . '='. urlencode('json')
        . '&' . urlencode('limit') . '=' . urlencode('100')
        . '&' . urlencode('offset') . '=' . urlencode($nodes[$i]);
        $curl_arr[$i] = curl_init($url);
        curl_setopt($curl_arr[$i], CURLOPT_RETURNTRANSFER, true);
        curl_setopt($curl_arr[$i], CURLOPT_HEADER, FALSE);
        curl_setopt($curl_arr[$i], CURLOPT_CUSTOMREQUEST, 'GET');
        curl_multi_add_handle($master, $curl_arr[$i]);
    }

    do {
        curl_multi_exec($master,$running);
    } while($running > 0);

    // Combines each output into json and merges the invoice attribute together
    for($i = 0; $i < $node_count; $i++)
    {
        $curl_json = json_decode(curl_multi_getcontent  ( $curl_arr[$i]  ));
        $array_out = array_merge($array_out, $curl_json->invoice);
    }

    return $array_out;
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

// xml generated to be ingested by Alma 
$xml_ERP = new SimpleXMLElement('<?xml version="1.0" encoding="UTF-8"?><payment_confirmation_data></payment_confirmation_data>');
$xml_ERP->addAttribute("xmlns", "http://com/exlibris/repository/acq/xmlbeans");
$xml_ERP_invoice_list = $xml_ERP->addChild('invoice_list');

// Dafis Oracle SQL Information 
// TODO put this in a better place
$db_dafis = "(
    DESCRIPTION=(
        ADDRESS_LIST=(
            ADDRESS=(COMMUNITY=TCP.ucdavis.edu)
            (PROTOCOL=TCP)
            (Host=afs-oda3b.ucdavis.edu)
            (Port=1521)
        )
    )
    (
        CONNECT_DATA=(SID=dsuat)
        (GLOBAL_NAME=fis_ds_uat.ucdavis.edu)
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
                      where vendor_invoice_num LIKE :vend_num
                      order by doc_num
EOT;

$statement = $dafis_dbh->prepare($kfs_query);

$invoice_array = get_waiting_invoices();

$count = 0;
// look at the xml directory and look through each xml file
foreach ($invoice_array as $invoice) {
    $statement->execute(
        array(':vend_num' => "$invoice->number")
    );  
    if($row = $statement->fetch()){
        //Add xml info needed for ERP
        $xml_invoice = $xml_ERP_invoice_list->addChild('invoice');
        $xml_invoice->addChild('invoice_number', $invoice->number);
        $xml_invoice->addChild('unique_identifier', $invoice->id);
        $xml_invoice->addChild('invoice_date',$invoice->invoice_date);
        $xml_invoice->addChild('vendor_code', $invoice->vendor);

        //$vend_id = vend_addcode_to_dafis($invoice->vendor_additional_code);

        // loop through result rows updating alma via the Web APIs
        //Update Payment information
        $xml_invoice->addChild('payment_status', "PAID");
        $xml_invoice->addChild('payment_voucher_date', $row["PAYMENT_ENTERED_DATE"]);
        $xml_invoice->addChild('payment_voucher_number', $row["CHECK_NUM"]);
        $amt = $xml_invoice->addChild('voucher_amount');
        $amt->addChild('currency', 'USD');
        $amt->addChild('sum', $row['PAYMENT_TOTAL_AMT']);
        
        $count++;
    }
}
print "Total invoices in \"Waiting for payment\": " . count($invoice_array) . "\n";
print "Total invoices found in FISDIS: $count\n"; 
if ($count > 0) {
    // Writes the ERP input xml to input/ 
    $xml_ERP->asXML("input/" . time() .  '.input.xml');
    print "Processed : ERP input XML generated.\n";
} else {
    print "No invoices needed to be updated.\n";
}
?>

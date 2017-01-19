<?php
/*
 *  Class FTPClient
 *  
 *  Purpose:  To provide a simpler interface for connecting to
 *          and interacting with FTP servers via PHP commands.
 *          Includes logging to help users identify when
 *          there is a problem, and what that problem is.
 *  Logging: The logging is session/class based. It is not
 *          stored in any file or database. 
 */
if (!class_exists('FTPClient')){
    class FTPClient{
        private  $conn_id;
        private $logged_in=FALSE;
        private $server_name='localhost';
        private $ftp_user="michael";
        private $ftp_pwd="x2s1a!/@";
        private $message_array = array();
        
        private $arr_ascii;
        
        public function __construct(){
            $this->arr_ascii =  array('xml','txt','csv','apfeed');
        }
        public function __deconstruct() {
            if ($this->conn_id) {
                ftp_close($this->conn_id);
            }
        }
        private function log_message($msg){
            $this->message_array[] = $msg;
        }
        public function get_messages(){
            return $this->message_array;            
        }
        public function connect ($server='', $ftpUser='',$ftpPwd='',$isPassive=FALSE,$use_ssl=FALSE){
        
            if ($server!=='') $this->server_name = $server;
            if ($ftpUser!=='') $this->ftp_user = $ftpUser;
            if ($ftpPwd!=='') $this->ftp_pwd = $ftpPwd;
            
            // *** Set up connection
            if ($use_ssl===TRUE){
                $this->conn_id = ftp_ssl_connect($server) or $this->log_message("Could not connect to FTP server $server");
            } else {
                $this->conn_id = ftp_connect($server) or $this->log_message("Could not connect to FTP server $server");
            }            
        
            // *** Login with username and password
            $loginResult = ftp_login($this->conn_id, $this->ftp_user, $this->ftp_pwd);
        
            // *** Sets passive mode on/off (default off)
            ftp_pasv($this->conn_id, $isPassive);
        
            // *** Check connection
            if ((!$this->conn_id) || (!$loginResult)) {
                $this->log_message('FTP connection has failed!');
                $this->log_message('Attempted to connect to ' . $server . ' for user ' . $ftpUser, TRUE);
                return FALSE;
            } else {
                $this->log_message('Connected to ' . $server . ', for user ' . $ftpUser);
                $this->logged_in = TRUE;
                return TRUE;
            }
        }       
        public function mkDir($dirname){
            // *** If creating a directory is successful...
            if (ftp_mkdir($this->conn_id, $dirname)) {            
                $this->log_message('Remote directory "' . $dirname . '" created successfully');
                return TRUE;            
            } else {            
                // *** ...Else, FAIL.
                $this->log_message('Failed creating directory "' . $dirname . '"');
                return FALSE;
            }
        }
        
        public function upload($from_file,$to_file){
            // *** Set the transfer mode
            $path_parts = explode('/',$from_file);
            $file_parts = explode('.', end($path_parts));
            $prefix = array_shift($file_parts);
            $extension = end($file_parts);
            
            if (in_array($prefix,$this->arr_ascii) || in_array($extension, $this->arr_ascii)) {
                $mode = FTP_ASCII;
            } else {
                $mode = FTP_BINARY;
            }
        
            // *** Upload the file
            $upload = ftp_put($this->conn_id, $to_file, $from_file, $mode);
        
            // *** Check upload status
            if (!$upload) {
        
                $this->log_message('FTP upload has failed!');
                return FALSE;
        
            } else {
                $this->log_message('Uploaded "' . $from_file . '" as "' . $to_file);
                return TRUE;
            }
        }
        public function download ($from_file, $to_file){
        
            // *** Set the transfer mode
            $fileParts = explode('.', $from_file);
            $extension = end($fileParts);
            
            if (in_array($extension, $this->arr_ascii)) {
                $mode = FTP_ASCII;
            } else {
                $mode = FTP_BINARY;
            }
        
            // try to download $remote_file and save it to $handle
            if (ftp_get($this->conn_id, $to_file, $from_file, $mode, 0)) {
        
                return TRUE;
                $this->log_message(' file "' . $to_file . '" successfully downloaded');
            } else {
        
                return FALSE;
                $this->log_message('There was an error downloading file "' . $from_file . '" to "' . $to_file . '"');
            }
        
        }
        public function cd($dirname) {
            if (ftp_chdir($this->conn_id, $dirname)) {
                $this->log_message('Current directory is now: ' . ftp_pwd($this->conn_id));
                return TRUE;
            } else {
                $this->log_message('Couldn\'t change directory');
                return FALSE;
            }
        }
        
        public function dir($dirname = '.', $parameters = '-la'){
            // get contents of the current directory
            $contentsArray = ftp_nlist($this->conn_id, $parameters . '  ' . $dirname);
        
            return $contentsArray;
        }
        
        public function get_mod_date($filename){
            $last_mod = ftp_mdtm($this->conn_id,$filename);
            if ($last_mod != -1){
                $this->log_message("File $filename last modified $last_mod");
                return $last_mod;
            } else {
                $this->log_message("Could not get last modified for $filename");
            }
        }
        
        public function list_files($path){
            if (is_array($children = @ftp_rawlist($this->conn_id, $path))) {
                $files = array();
    
                foreach ($children as $child) {
                    $chunks = preg_split("/\s+/", $child);
                    list($item['rights'], $item['number'], $item['user'], $item['group'], $item['size'], $item['month'], $item['day'], $item['time']) = $chunks;
                    $item['type'] = $chunks[0]{0} === 'd' ? 'directory' : 'file';
                    $item['name'] = $chunks[8];
                    $item['modified']= ftp_mdtm($this->conn_id, $item['name']);
                    array_splice($chunks, 0, 8);
                    $files[implode(" ", $chunks)] = $item;
                }
    
                return $files;
            } 
        }
        
        public function del($filename){
            if (ftp_delete($this->conn_id,$filename)){
                $this->log_message("File $filename deleted succesffully");
            } else {
                $this->log_message("File $filename could not be deleted");
            }
        }
        
    } // end class
        
} // end if class exists
?>
<?php
/*
SSH2 PHP5 OOP Class
Copyright (C) 2011 - Jine (http://jine.se)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/
/**
*
*	@desc Simple PHP5 Class for usage with libssh2-php (ssh2)
*	@author Jim Nelin & Jine - http://jine.se
*	@date 2011-02-09
*
*	Example;
*	----------------------------------------------
*	require_once("SSH2.php");
*
*	$ssh = new SSH2("hostname.com");
*	
*	// With auth with password:
*	$ssh->auth("root", "xxx");
*	
*	// Or public key:
*	$ssh->auth("root", "~/.ssh/id_rsa.pub", "~/.ssh/id_rsa", "keypassword");
*	
*	$ssh->exec("id");
*	echo $ssh->output();
*	----------------------------------------------
*	
**/

class SSH2 {

	var $ssh;
	var $stream;
	var $errors = array();
		
	function __construct($host, $port=22) {
	    try{
    		if (!$this->ssh = ssh2_connect($host, $port)) {
    			return false; 
    		}
	    } catch(Exception $e){
	        $errors[] = "Error $e->getCode(): $e->getMessage() on line $e->getLine() of $e->getFile()::(constructor)";
	        return FALSE;
	    }
	}
	

	function auth($username, $auth, $private = null, $secret = null) {
	    try{
    		if(is_file($auth) && is_readable($auth) && isset($private)) {
    			// If $auth is a file, and $private is set, try pubkey auth
    			if(!ssh2_auth_pubkey_file($this->ssh, $username, $auth, $private, $secret)) {
    				return false;
    			}
    			
    		} else {
    		
    			// If not pubkey auth, auth with password
    			if(!ssh2_auth_password($this->ssh, $username, $auth)) {
    				return false;
    			}
    			
    		}
    		
    		return true;
		} catch(Exception $e){
		    $errors[] = "Error $e->getCode(): $e->getMessage() on line $e->getLine() of $e->getFile()::(auth)";
		    return FALSE;
		}
	}

	function send($local, $remote, $perm) {
		if(!ssh2_scp_send($this->ssh, $local, $remote, $perm)) { 
			return false; 
		}
			
		return true;
	}

	function get($remote, $local) {
		if(ssh2_scp_recv($this->ssh, $remote, $local)) {
			return false;
		} 
	
		return true;
	}

	function cmd($cmd, $blocking = true) {
		$this->stream = ssh2_exec($this->ssh, $cmd);
		stream_set_blocking($this->stream, $blocking);
	}
	
	// Just an aliasfunction for $this->cmd
	function exec($cmd, $blocking = true) {
		$this->cmd($cmd, $blocking = true);
	}

	function output() {			   
		return stream_get_contents($this->stream);
	}

}
<?php
$update_alma = "/home/gogothee/work/check_processing/update_alma.py";
$args = "--output-dir /home/almadafis/input/ --log-level INFO";
$command = escapeshellcmd("$update_alma $args");
$output = shell_exec($command);
echo $output;

?>

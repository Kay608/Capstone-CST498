<?php
$host = "d6vscs19jtah8iwb.cbetxkdyhwsb.us-east-1.rds.amazonaws.com";      // or JawsDB host
$user = "pibeadwopo2puu2w";           // your DB username
$pass = "ia58h6oid99au8x4";               // your DB password
$db   = "cdzpl48ljf6v83hu";           // your database name

$conn = new mysqli($host, $user, $pass, $db);

if ($conn->connect_error) {
    die("Connection failed: " . $conn->connect_error);
}
?>
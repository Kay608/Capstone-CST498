<?php
include "db_connect.php"; // <-- must match your database name

$conn = new mysqli($servername, $username, $password, $dbname);

// Check connection
if ($conn->connect_error) {
    die("Connection failed: " . $conn->connect_error);
}

// Get form data
$banid  = $_POST['banid'];
$fname  = $_POST['fname'];
$lname  = $_POST['lname'];
$email  = $_POST['email'];

// Handle image upload
$targetDir = "uploads/";
if (!is_dir($targetDir)) {
    mkdir($targetDir, 0777, true);
}
$imageName = basename($_FILES["image"]["name"]);
$targetFilePath = $targetDir . time() . "_" . $imageName;

if (move_uploaded_file($_FILES["image"]["tmp_name"], $targetFilePath)) {
    // Insert into users table
    $sql = "INSERT INTO user_info (banid, fname, lname, email, image) 
            VALUES ('$banid', '$fname', '$lname', '$email', '$targetFilePath')";

    if ($conn->query($sql) === TRUE) {
        header("Location: add_user.php?success=1");
        exit();
    } else {
        header("Location: add_user.php?error=db");
        exit();
    }
} else {
    header("Location: add_user.php?error=upload");
    exit();
}

$conn->close();
?>

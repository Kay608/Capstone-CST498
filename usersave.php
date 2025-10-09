<?php
// Database connection
$servername = "localhost";
$username = "root"; // default in XAMPP
$password = ""; // default in XAMPP
$dbname = "test"; 

$conn = new mysqli($servername, $username, $password, $dbname);

// Check connection
if ($conn->connect_error) {
    die("Connection failed: " . $conn->connect_error);
}

// Get form data
$banid = $_POST['banid'];
$fname = $_POST['fname'];
$lname = $_POST['lname'];
$email = $_POST['email'];

// Handle image upload
$targetDir = "uploads/";  // create this folder in your project
if (!is_dir($targetDir)) {
    mkdir($targetDir, 0777, true);
}
$imageName = basename($_FILES["image"]["name"]);
$targetFilePath = $targetDir . time() . "_" . $imageName;

if (move_uploaded_file($_FILES["image"]["tmp_name"], $targetFilePath)) {
    // Insert into database
    $sql = "INSERT INTO user_info (banid, fname, lname, email, img) VALUES ('$banid,'$fname','$lname' '$email', '$targetFilePath')";

    if ($conn->query($sql) === TRUE) {
        echo "New user added successfully!<br>";
        echo "<a href='add_user.html'>Add another user</a>";
    } else {
        echo "Error: " . $conn->error;
    }
} else {
    echo "Error uploading image.";
}

$conn->close();
?>


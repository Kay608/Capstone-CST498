import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:http/http.dart' as http;
import 'package:path/path.dart' as p;
import 'package:mime/mime.dart';
import 'package:http_parser/http_parser.dart'; // <-- keep this import

void main() {
  runApp(const FaceUploadApp());
}

class FaceUploadApp extends StatelessWidget {
  const FaceUploadApp({super.key}); // use super parameter

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Face Recognition Upload',
      theme: ThemeData(
        primarySwatch: Colors.deepPurple,
      ),
      home: const FaceUploadScreen(),
    );
  }
}

class FaceUploadScreen extends StatefulWidget {
  const FaceUploadScreen({super.key}); // use super parameter

  @override
  FaceUploadScreenState createState() => FaceUploadScreenState();
}

class FaceUploadScreenState extends State<FaceUploadScreen> { // Public class
  File? _image;
  final picker = ImagePicker();
  final TextEditingController _nameController = TextEditingController();

  // ⛓️ Replace with your Raspberry Pi’s IP
  final String serverUrl = "http://192.168.1.100:5000/upload";
  // Add your server's delete endpoint
  final String deleteUrl = "http://192.168.1.100:5000/delete_face";

  // For demo: store token in memory (replace with secure storage in production)
  String? _token;

  Future<void> _deleteFace() async {
    if (_nameController.text.isEmpty) return;
    // For demo: prompt for token if not set
    if (_token == null) {
      final token = await _promptForToken();
      if (token == null) return;
      setState(() { _token = token; });
    }
    var uri = Uri.parse(deleteUrl);
    var response = await http.delete(
      uri,
      headers: { 'Authorization': 'Bearer "+_token!+"' },
    );
    if (response.statusCode == 200) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Face data deleted successfully!")),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Delete failed: ${response.body}")),
      );
    }
  }

  Future<String?> _promptForToken() async {
    String? token;
    await showDialog(
      context: context,
      builder: (context) {
        final controller = TextEditingController();
        return AlertDialog(
          title: const Text('Enter your auth token'),
          content: TextField(
            controller: controller,
            decoration: const InputDecoration(labelText: 'Token'),
          ),
          actions: [
            TextButton(
              onPressed: () {
                token = controller.text;
                Navigator.of(context).pop();
              },
              child: const Text('OK'),
            ),
          ],
        );
      },
    );
    return token?.isNotEmpty == true ? token : null;
  }

  Future<void> _pickImage() async {
    final pickedFile = await picker.pickImage(source: ImageSource.camera);

    if (pickedFile != null) {
      setState(() {
        _image = File(pickedFile.path);
      });
    }
  }

  Future<void> _uploadImage() async {
    if (_image == null || _nameController.text.isEmpty) return;

    var uri = Uri.parse(serverUrl);
    var request = http.MultipartRequest('POST', uri);

    request.fields['name'] = _nameController.text;

    request.files.add(await http.MultipartFile.fromPath(
      'image',
      _image!.path,
      contentType: MediaType.parse(lookupMimeType(_image!.path) ?? "image/jpeg"),
    ));

    var response = await request.send();

    if (response.statusCode == 200) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Image uploaded successfully!")), // const
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Upload failed.")), // const
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Face Registration")), // const
      body: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            _image != null
                ? Image.file(_image!, height: 200)
                : const Text("No image selected."), // const
            const SizedBox(height: 20), // const
            TextField(
              controller: _nameController,
              decoration: const InputDecoration( // const
                labelText: "Enter your name",
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 20), // const
            ElevatedButton(
              onPressed: _pickImage,
              child: const Text("Take Photo"), // const
            ),
            const SizedBox(height: 10), // const
            ElevatedButton(
              onPressed: _uploadImage,
              child: const Text("Upload Photo"), // const
            ),
            const SizedBox(height: 10),
            ElevatedButton(
              onPressed: _deleteFace,
              style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
              child: const Text("Delete My Face"),
            ),
          ],
        ),
      ),
    );
  }
}

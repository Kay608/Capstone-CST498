import 'dart:io';
import 'dart:convert';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:http/http.dart' as http;
import 'package:path/path.dart' as p;
import 'package:mime/mime.dart';
import 'package:http_parser/http_parser.dart'; // <-- keep this import
import 'package:multicast_dns/multicast_dns.dart';

void main() {
  runApp(const FaceUploadApp());
}

class FaceUploadApp extends StatelessWidget {
  const FaceUploadApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Face Recognition Upload',
      theme: ThemeData(
        primarySwatch: Colors.deepPurple,
      ),
      home: const HomeScreen(),
    );
  }
}

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Delivery Bot App')),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            ElevatedButton(
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => const FaceUploadScreen()),
              ),
              child: const Text('Face Registration'),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => const TrackRobotScreen()),
              ),
              child: const Text('Track Robot'),
            ),
          ],
        ),
      ),
    );
  }
}

class FaceUploadScreen extends StatefulWidget {
  const FaceUploadScreen({super.key});

  @override
  FaceUploadScreenState createState() => FaceUploadScreenState();
}

class FaceUploadScreenState extends State<FaceUploadScreen> {
  File? _image;
  final picker = ImagePicker();
  final TextEditingController _nameController = TextEditingController();

  // Unified backend base URL
  String backendBaseUrl = "http://appservice.local:5001";
  String registerFaceUrl = "http://appservice.local:5001/register_face";
  String uploadImageUrl = "http://appservice.local:5001/upload_image";
  String deleteFaceUrl = "http://appservice.local:5001/delete_face";
  // Navigation endpoints (for future use)
  String goalUrl = "http://appservice.local:5001/goal";
  String statusUrl = "http://appservice.local:5001/status";

  bool _isUploading = false;
  bool _isDeleting = false;

  @override
  void initState() {
    super.initState();
    _discoverBackend();
  }

  Future<void> _discoverBackend() async {
    try {
      final MDnsClient client = MDnsClient(rawDatagramSocketFactory: (dynamic host, int port, {bool? reuseAddress, bool? reusePort, int? ttl}) {
        return RawDatagramSocket.bind(host, port, reuseAddress: true, reusePort: false, ttl: ttl ?? 1);
      });
      await client.start();
      await for (final PtrResourceRecord ptr in client.lookup<PtrResourceRecord>(ResourceRecordQuery.serverPointer('_http._tcp.local.'))) {
        if (ptr.domainName == 'appservice._http._tcp.local.') {
          await for (final SrvResourceRecord srv in client.lookup<SrvResourceRecord>(ResourceRecordQuery.service(ptr.domainName))) {
            await for (final IPAddressResourceRecord ip in client.lookup<IPAddressResourceRecord>(ResourceRecordQuery.addressIPv4(srv.target))) {
              setState(() {
                backendBaseUrl = 'http://${ip.address.address}:${srv.port}';
                registerFaceUrl = '$backendBaseUrl/register_face';
                uploadImageUrl = '$backendBaseUrl/upload_image';
                deleteFaceUrl = '$backendBaseUrl/delete_face';
                goalUrl = '$backendBaseUrl/goal';
                statusUrl = '$backendBaseUrl/status';
              });
              client.stop();
              return;
            }
          }
        }
      }
      client.stop();
    } catch (e) {
      // If discovery fails, fallback to default
    }
  }

  Future<void> _pickImage() async {
    final pickedFile = await picker.pickImage(
      source: Platform.isAndroid || Platform.isIOS
          ? ImageSource.camera
          : ImageSource.gallery,
    );

    if (pickedFile != null) {
      setState(() {
        _image = File(pickedFile.path);
      });
    }
  }

  Future<void> _uploadImage() async {
    if (_image == null || _nameController.text.isEmpty) return;
    setState(() {
      _isUploading = true;
    });
    try {
      var uri = Uri.parse(registerFaceUrl);
      var request = http.MultipartRequest('POST', uri);
      request.fields['name'] = _nameController.text;
      request.files.add(await http.MultipartFile.fromPath(
        'image',
        _image!.path,
        contentType: MediaType.parse(lookupMimeType(_image!.path) ?? "image/jpeg"),
      ));
      var response = await request.send().timeout(const Duration(seconds: 10));
      if (response.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Image uploaded successfully!")),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Upload failed.")),
        );
      }
    } on TimeoutException {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Upload timed out. Check your connection.")),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Upload error: $e")),
      );
    } finally {
      setState(() {
        _isUploading = false;
      });
    }
  }

  Future<void> _deleteFace() async {
    if (_nameController.text.isEmpty) return;
    setState(() {
      _isDeleting = true;
    });
    try {
      var uri = Uri.parse(deleteFaceUrl);
      var response = await http.delete(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: '{"name": "${_nameController.text}"}',
      ).timeout(const Duration(seconds: 10));
      if (response.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Face data deleted successfully!")),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Delete failed: " + response.body)),
        );
      }
    } on TimeoutException {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Delete timed out. Check your connection.")),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Delete error: $e")),
      );
    } finally {
      setState(() {
        _isDeleting = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Face Registration")),
      body: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            _image != null
                ? Image.file(_image!, height: 200)
                : const Text("No image selected."),
            const SizedBox(height: 20),
            TextField(
              controller: _nameController,
              decoration: const InputDecoration(
                labelText: "Enter your name",
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: _pickImage,
              child: const Text("Take Photo"),
            ),
            const SizedBox(height: 10),
            ElevatedButton(
              onPressed: _isUploading ? null : _uploadImage,
              child: _isUploading
                  ? const CircularProgressIndicator()
                  : const Text("Upload Photo"),
            ),
            const SizedBox(height: 10),
            ElevatedButton(
              onPressed: _isDeleting ? null : _deleteFace,
              style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
              child: _isDeleting
                  ? const CircularProgressIndicator()
                  : const Text("Delete My Face"),
            ),
          ],
        ),
      ),
    );
  }
}

class TrackRobotScreen extends StatefulWidget {
  const TrackRobotScreen({super.key});
  @override
  State<TrackRobotScreen> createState() => _TrackRobotScreenState();
}

class _TrackRobotScreenState extends State<TrackRobotScreen> {
  final String statusUrl = "http://192.168.1.100:5001/status";
  Map<String, dynamic>? robotStatus;
  bool loading = false;

  Future<void> fetchStatus() async {
    setState(() {
      loading = true;
    });
    try {
      final response = await http.get(Uri.parse(statusUrl)).timeout(const Duration(seconds: 10));
      if (response.statusCode == 200) {
        setState(() {
          robotStatus = Map<String, dynamic>.from(
            response.body.isNotEmpty
                ? (response.body.startsWith('{') ? jsonDecode(response.body) : {})
                : {},
          );
        });
      }
    } on TimeoutException {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Status fetch timed out. Check your connection.")),
      );
    } catch (_) {}
    setState(() {
      loading = false;
    });
  }

  @override
  void initState() {
    super.initState();
    fetchStatus();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Track Robot')),
      body: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ElevatedButton(
              onPressed: fetchStatus,
              child: const Text('Refresh Status'),
            ),
            const SizedBox(height: 20),
            loading
                ? const CircularProgressIndicator()
                : robotStatus == null
                    ? const Text('No status data.')
                    : Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('State: ' + robotStatus!["state"].toString()),
                          Text('Last Goal: ' + robotStatus!["last_goal"].toString()),
                          Text('Coords: ' + robotStatus!["coords"].toString()),
                          Text('GPS: ' + robotStatus!["gps"].toString()),
                          Text('Last Update: ' + robotStatus!["last_update"].toString()),
                        ],
                      ),
          ],
        ),
      ),
    );
  }
}

import SwiftUI
import UniformTypeIdentifiers

/// A SwiftUI wrapper around UIDocumentPickerViewController.
/// Used in UploadView to let the user pick their Apple Health export.xml file.
struct DocumentPicker: UIViewControllerRepresentable {
    @Binding var selectedURL: URL?
    var onDismiss: () -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    func makeUIViewController(context: Context) -> UIDocumentPickerViewController {
        // Accept XML files and any generic data (covers .xml.zip from Health export)
        let types: [UTType] = [.xml, .data, .item]
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: types)
        picker.delegate = context.coordinator
        picker.allowsMultipleSelection = false
        picker.shouldShowFileExtensions = true
        return picker
    }

    func updateUIViewController(_ uiViewController: UIDocumentPickerViewController, context: Context) {}

    // MARK: - Coordinator

    class Coordinator: NSObject, UIDocumentPickerDelegate {
        let parent: DocumentPicker

        init(_ parent: DocumentPicker) {
            self.parent = parent
        }

        func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
            guard let url = urls.first else { return }

            // Request access to the security-scoped resource
            let accessing = url.startAccessingSecurityScopedResource()
            defer {
                if accessing { url.stopAccessingSecurityScopedResource() }
            }

            // Copy file to a temp location so we can read it freely
            let tempURL = FileManager.default.temporaryDirectory
                .appendingPathComponent(url.lastPathComponent)

            do {
                if FileManager.default.fileExists(atPath: tempURL.path) {
                    try FileManager.default.removeItem(at: tempURL)
                }
                try FileManager.default.copyItem(at: url, to: tempURL)
                parent.selectedURL = tempURL
            } catch {
                print("DocumentPicker copy error: \(error)")
                // Fall back to original URL
                parent.selectedURL = url
            }

            parent.onDismiss()
        }

        func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
            parent.onDismiss()
        }
    }
}

import SwiftUI
import UniformTypeIdentifiers

struct DocumentPicker: UIViewControllerRepresentable {
    @Binding var selectedURL: URL?
    var onDismiss: () -> Void
    
    func makeUIViewController(context: Context) -> UIDocumentPickerViewController {
        let types: [UTType] = [.commaSeparatedText, .plainText, .json]
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: types)
        picker.delegate = context.coordinator
        return picker
    }
    
    func updateUIViewController(_ uiViewController: UIDocumentPickerViewController, context: Context) {}
    
    func makeCoordinator() -> Coordinator {
        Coordinator(selectedURL: $selectedURL, onDismiss: onDismiss)
    }
    
    class Coordinator: NSObject, UIDocumentPickerDelegate {
        @Binding var selectedURL: URL?
        let onDismiss: () -> Void
        
        init(selectedURL: Binding<URL?>, onDismiss: @escaping () -> Void) {
            _selectedURL = selectedURL
            self.onDismiss = onDismiss
        }
        
        func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
            selectedURL = urls.first
            onDismiss()
        }
    }
}

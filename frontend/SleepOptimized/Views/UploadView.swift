import SwiftUI
import UniformTypeIdentifiers

struct UploadView: View {
    @State private var selectedFile: URL?
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header
            Button(action: { dismiss() }) {
                Image(systemName: "chevron.left")
                    .font(.system(size: 24, weight: .medium))
                    .foregroundColor(Color(hex: "286EF1"))
            }
            .padding(.bottom, 8)
            
            Text("Upload Health Data")
                .font(.system(size: 28, weight: .bold))
                .foregroundColor(.black)
            
            Text("Step 1 of 2")
                .font(.system(size: 14, weight: .regular))
                .foregroundColor(Color(hex: "6C757D"))
                .padding(.top, 4)
            
            Rectangle()
                .fill(Color(hex: "DEE2E6"))
                .frame(height: 1)
                .padding(.top, 12)
                .padding(.bottom, 24)
            
            Text("Upload Data")
                .font(.system(size: 18, weight: .medium))
                .foregroundColor(.black)
                .padding(.bottom, 16)
            
            FileUploadBox(selectedFile: $selectedFile)
                .padding(.bottom, 32)
            
            Spacer()
            
            NavigationLink(destination: PreferencesView()) {
                Text("Next")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
                    .background(Color(hex: "286EF1"))
                    .clipShape(RoundedRectangle(cornerRadius: 25))
            }
        }
        .padding(24)
        .background(Color.white)
        .navigationBarBackButtonHidden(true)
    }
}

struct FileUploadBox: View {
    @Binding var selectedFile: URL?
    @State private var showingFilePicker = false
    
    var body: some View {
        Button(action: { showingFilePicker = true }) {
            VStack(spacing: 12) {
                Image(systemName: "square.and.arrow.up")
                    .font(.system(size: 48))
                    .foregroundColor(Color(hex: "6C757D"))
                Text("Tap to upload")
                    .font(.system(size: 16))
                    .foregroundColor(Color(hex: "6C757D"))
                Text("(CSV, TXT, or JSON)")
                    .font(.system(size: 14))
                    .foregroundColor(Color(hex: "ADB5BD"))
                if let file = selectedFile {
                    Text(file.lastPathComponent)
                        .font(.system(size: 12))
                        .foregroundColor(Color(hex: "286EF1"))
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
            }
            .frame(maxWidth: .infinity)
            .frame(minHeight: 200)
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .strokeBorder(style: StrokeStyle(lineWidth: 2, dash: [8]))
                    .foregroundColor(Color(hex: "DEE2E6"))
            )
        }
        .buttonStyle(.plain)
        .sheet(isPresented: $showingFilePicker) {
            DocumentPicker(selectedURL: $selectedFile) {
                showingFilePicker = false
            }
        }
    }
}

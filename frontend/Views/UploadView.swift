import SwiftUI
import UniformTypeIdentifiers

struct UploadView: View {
    @EnvironmentObject var api: SleepAPIManager
    @Environment(\.dismiss) private var dismiss

    @State private var selectedFile: URL?
    @State private var isUploading = false
    @State private var uploadError: String?
    @State private var navigateToPreferences = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            if !api.isEmailVerified {
                HStack {
                    Image(systemName: "envelope.badge")
                        .foregroundColor(.orange)
                    Text("Please verify your email to upload data.")
                        .font(.system(size: 14, weight: .semibold))
                }
                .padding(12)
                .background(Color.yellow.opacity(0.2))
                .cornerRadius(8)
                .padding(.bottom, 12)
            }
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
                .font(.system(size: 14))
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
                .padding(.bottom, 8)

            Text("Export from the Health app: tap your profile picture → Export All Health Data")
                .font(.system(size: 13))
                .foregroundColor(Color(hex: "6C757D"))
                .padding(.bottom, 16)

            FileUploadBox(selectedFile: $selectedFile)
                .padding(.bottom, 16)

            if let error = uploadError {
                Text(error)
                    .font(.system(size: 13))
                    .foregroundColor(.red)
                    .padding(.bottom, 8)
            }

            Spacer()

            // Triggers upload then navigates on success
            Button(action: handleUpload) {
                HStack(spacing: 8) {
                    if isUploading {
                        ProgressView().tint(.white)
                    }
                    Text(isUploading ? "Uploading..." : "Next")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(.white)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 16)
                .background(selectedFile != nil && !isUploading
                    ? Color(hex: "286EF1")
                    : Color(hex: "ADB5BD"))
                .clipShape(RoundedRectangle(cornerRadius: 25))
            }
            .disabled(selectedFile == nil || isUploading || !api.isEmailVerified)


        }
        .padding(24)
        .background(Color.white)
        .navigationBarBackButtonHidden(true)
        .navigationDestination(isPresented: $navigateToPreferences) {
            PreferencesView()
                .navigationBarBackButtonHidden(true)
        }
    }

    private func handleUpload() {
        guard api.isEmailVerified else { return }
        guard let fileURL = selectedFile else { return }
        isUploading = true
        uploadError = nil

        Task {
            do {
                try await api.uploadHealthData(fileURL: fileURL)
                await api.checkUserDataExists() // Update user data state after upload
                navigateToPreferences = true
            } catch {
                uploadError = error.localizedDescription
            }
            isUploading = false
        }
    }
}

struct FileUploadBox: View {
    @Binding var selectedFile: URL?
    @State private var showingFilePicker = false

    var body: some View {
        Button(action: { showingFilePicker = true }) {
            VStack(spacing: 12) {
                Image(systemName: selectedFile != nil ? "checkmark.circle.fill" : "square.and.arrow.up")
                    .font(.system(size: 48))
                    .foregroundColor(selectedFile != nil ? Color(hex: "22C55E") : Color(hex: "6C757D"))
                Text(selectedFile != nil ? "File selected" : "Tap to upload")
                    .font(.system(size: 16))
                    .foregroundColor(Color(hex: "6C757D"))
                Text("Apple Health export.xml")
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
                    .strokeBorder(
                        style: StrokeStyle(lineWidth: 2, dash: [8]),
                        antialiased: true
                    )
                    .foregroundColor(selectedFile != nil
                        ? Color(hex: "22C55E")
                        : Color(hex: "DEE2E6"))
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

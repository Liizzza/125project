import SwiftUI
import UniformTypeIdentifiers

struct UploadView: View {
    @EnvironmentObject var api: SleepAPIManager
    @Environment(\.dismiss) private var dismiss

    @State private var selectedFile: URL?
    @State private var isUploading = false
    @State private var isProcessingOnServer = false
    @State private var uploadError: String?
    @State private var navigateToPreferences = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Email Verification Banner
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

            // Status Messages
            Group {
                if let error = uploadError {
                    Text(error)
                        .font(.system(size: 13))
                        .foregroundColor(.red)
                } else if isProcessingOnServer {
                    HStack {
                        ProgressView()
                            .padding(.trailing, 8)
                        Text("Server is processing records...")
                            .font(.system(size: 13))
                            .foregroundColor(Color(hex: "286EF1"))
                    }
                } else if api.hasUserData {
                    Text("✅ Data already uploaded. Ready to proceed.")
                        .font(.system(size: 13))
                        .foregroundColor(.green)
                }
            }
            .padding(.bottom, 8)

            Spacer()

            // Main Action Button
            Button(action: handleUpload) {
                HStack(spacing: 8) {
                    if isUploading || isProcessingOnServer {
                        ProgressView().tint(.white)
                    }
                    Text(buttonText)
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(.white)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 16)
                .background(isButtonEnabled ? Color(hex: "286EF1") : Color(hex: "ADB5BD"))
                .clipShape(RoundedRectangle(cornerRadius: 25))
            }
            .disabled(!isButtonEnabled)

        }
        .padding(24)
        .background(Color.white)
        .navigationBarBackButtonHidden(true)
        .navigationDestination(isPresented: $navigateToPreferences) {
            PreferencesView()
                .navigationBarBackButtonHidden(true)
        }
        .onAppear {
            Task { await api.checkUserDataExists() }
        }
    }

    // MARK: - Computed Properties
    
    private var isButtonEnabled: Bool {
        (selectedFile != nil || api.hasUserData) && !isUploading && !isProcessingOnServer && api.isEmailVerified
    }
    
    private var buttonText: String {
        if isUploading { return "Uploading..." }
        if isProcessingOnServer { return "Processing..." }
        if api.hasUserData { return "Next" }
        return "Upload & Next"
    }

    // MARK: - Logic Helpers

    private func handleUpload() {
        if api.hasUserData {
            navigateToPreferences = true
            return
        }

        guard let fileURL = selectedFile else { return }
        
        isUploading = true
        uploadError = nil

        Task {
            do {
                try await api.uploadHealthData(fileURL: fileURL)
                
                await MainActor.run {
                    isUploading = false
                    isProcessingOnServer = true
                }
                
                await startStatusPolling()
                
            } catch {
                await MainActor.run {
                    isUploading = false
                    uploadError = error.localizedDescription
                }
            }
        }
    }
    
    private func startStatusPolling() async {
        var isCompleted = false
        var retryCount = 0
        let maxRetries = 15
        
        while !isCompleted && retryCount < maxRetries {
            do {
                let status = try await api.getProcessingStatus()
                
                if status == "completed" {
                    isCompleted = true
                    await api.checkUserDataExists()
                    await MainActor.run {
                        isProcessingOnServer = false
                        navigateToPreferences = true
                    }
                } else if status == "failed" {
                    await MainActor.run {
                        isProcessingOnServer = false
                        uploadError = "Processing failed. Please try a different export file."
                    }
                    return
                }
                
                retryCount += 1
                // Added 'try?' to fix the "Errors not handled" error
                try? await Task.sleep(nanoseconds: 2 * 1_000_000_000)
                
            } catch {
                retryCount += 1
                try? await Task.sleep(nanoseconds: 2 * 1_000_000_000)
            }
        }
        
        if !isCompleted {
            await MainActor.run {
                isProcessingOnServer = false
                uploadError = "Processing timed out. Try clicking Next if success logs appeared."
                Task { await api.checkUserDataExists() }
            }
        }
    }
}

// MARK: - File Upload Subview

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
                
                Text("Apple Health export.zip")
                    .font(.system(size: 14))
                    .foregroundColor(Color(hex: "ADB5BD"))
                
                if let file = selectedFile {
                    Text(file.lastPathComponent)
                        .font(.system(size: 12))
                        .foregroundColor(Color(hex: "286EF1"))
                        .lineLimit(1)
                }
            }
            .frame(maxWidth: .infinity)
            .frame(minHeight: 200)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .strokeBorder(style: StrokeStyle(lineWidth: 2, dash: [8]))
                    .foregroundColor(selectedFile != nil ? Color(hex: "22C55E") : Color(hex: "DEE2E6"))
            )
        }
        .buttonStyle(.plain)
        .sheet(isPresented: $showingFilePicker) {
            // This now correctly points to your external Utilities/DocumentPicker.swift
            DocumentPicker(selectedURL: $selectedFile) {
                showingFilePicker = false
            }
        }
    }
}

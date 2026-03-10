import SwiftUI
import FirebaseCore

@main
struct SleepOptimizedApp: App {
    @StateObject private var firebaseAuth: FirebaseAuthManager
    @StateObject private var api: SleepAPIManager

    init() {
        FirebaseApp.configure()
        
        let auth = FirebaseAuthManager()
        _firebaseAuth = StateObject(wrappedValue: auth)
        _api = StateObject(wrappedValue: SleepAPIManager(firebaseAuth: auth))
    }

    @State private var verificationEmailSent = false

    var body: some Scene {
        WindowGroup {
            NavigationStack {
                Group {
                    if !firebaseAuth.isSignedIn {
                        LoginView(firebaseAuth: firebaseAuth)
                    } else if !api.isEmailVerified {
                        verificationView
                    } else if !api.hasUserData {
                        UploadView()
                    } else {
                        DashboardView()
                    }
                }
            }
            .environmentObject(firebaseAuth)
            .environmentObject(api)
            .task {
                if firebaseAuth.isSignedIn {
                    await api.checkUserDataExists()
                }
            }
        }
    }

    private var verificationView: some View {
        VStack(spacing: 24) {
            Image(systemName: "envelope.badge")
                .font(.system(size: 48))
                .foregroundColor(.blue)
            
            Text("Please verify your email to continue.")
                .font(.system(size: 18, weight: .semibold))
                .multilineTextAlignment(.center)
            
            if verificationEmailSent {
                Text("Verification email sent! Check your inbox.")
                    .foregroundColor(.green)
                    .font(.footnote)
            }
            
            VStack(spacing: 12) {
                Button("Resend Verification Email") {
                    api.sendEmailVerification { _ in
                        verificationEmailSent = true
                    }
                }
                .buttonStyle(.borderedProminent)
                
                Button("Check Again") {
                    Task {
                        await firebaseAuth.refreshToken()
                        await api.checkUserDataExists()
                        verificationEmailSent = false
                    }
                }
            }
            .padding(.top, 8)
        }
        .padding(40)
    }
}

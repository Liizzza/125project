import Foundation
import FirebaseAuth
import FirebaseCore
import Combine

public class FirebaseAuthManager: ObservableObject {
    @Published public var user: User?
    @Published public var idToken: String?
    @Published public var isAuthenticating = false
    @Published public var errorMessage: String?

    public init() {
        setupFirebase()
        listenForAuthChanges()
    }

    private func setupFirebase() {
        if FirebaseApp.app() == nil {
            FirebaseApp.configure()
        }
    }

    private func listenForAuthChanges() {
        _ = Auth.auth().addStateDidChangeListener { [weak self] _, user in
            Task { @MainActor in
                self?.user = user
                if let user = user {
                    do {
                        self?.idToken = try await user.getIDToken()
                    } catch {
                        self?.errorMessage = "Failed to get ID token: \(error.localizedDescription)"
                    }
                } else {
                    self?.idToken = nil
                }
            }
        }
    }

    public func refreshToken() async {
        guard let user = Auth.auth().currentUser else { return }
        do {
            let token = try await user.getIDToken(forcingRefresh: true)
            await MainActor.run { self.idToken = token }
        } catch {
            print("🔴 Token refresh error: \(error)")
        }
    }

    public func signUpWithEmail(_ email: String, password: String) async {
        await MainActor.run { isAuthenticating = true; errorMessage = nil }
        do {
            _ = try await Auth.auth().createUser(withEmail: email, password: password)
            if let user = Auth.auth().currentUser {
                let token = try await user.getIDToken()
                await MainActor.run {
                    self.user = user
                    self.idToken = token
                }
                // Send verification immediately on sign up
                try? await user.sendEmailVerification()
            }
        } catch {
            await MainActor.run { self.errorMessage = error.localizedDescription }
        }
        await MainActor.run { isAuthenticating = false }
    }

    public func signInWithEmail(_ email: String, password: String) async {
        await MainActor.run { isAuthenticating = true; errorMessage = nil }
        do {
            _ = try await Auth.auth().signIn(withEmail: email, password: password)
            if let user = Auth.auth().currentUser {
                let token = try await user.getIDToken()
                await MainActor.run {
                    self.user = user
                    self.idToken = token
                }
                
                // ADDED: Send verification email upon sign-in if they aren't verified yet
                if !user.isEmailVerified {
                    try? await user.sendEmailVerification()
                    print("📩 Verification email resent during sign-in")
                }
            }
        } catch {
            await MainActor.run { self.errorMessage = error.localizedDescription }
        }
        await MainActor.run { isAuthenticating = false }
    }

    public func sendEmailVerification() async throws {
        guard let user = Auth.auth().currentUser else { return }
        try await user.sendEmailVerification()
    }

    public func reloadCurrentUser() async throws {
        guard let user = Auth.auth().currentUser else { return }
        try await user.reload()
        let token = try await user.getIDToken()
        await MainActor.run {
            self.user = Auth.auth().currentUser
            self.idToken = token
        }
    }

    public func signInAnonymously() async {
        await MainActor.run { isAuthenticating = true; errorMessage = nil }
        do {
            _ = try await Auth.auth().signInAnonymously()
            if let user = Auth.auth().currentUser {
                let token = try await user.getIDToken()
                await MainActor.run { self.user = user; self.idToken = token }
            }
        } catch {
            await MainActor.run { self.errorMessage = error.localizedDescription }
        }
        await MainActor.run { isAuthenticating = false }
    }

    public func signOut() {
        try? Auth.auth().signOut()
        self.user = nil
        self.idToken = nil
    }

    public var isSignedIn: Bool {
        user != nil && idToken != nil
    }
}

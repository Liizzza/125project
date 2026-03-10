import SwiftUI

struct LoginView: View {
    @State private var email = ""
    @State private var password = ""
    @State private var isSignUp = false
    @ObservedObject var firebaseAuth: FirebaseAuthManager
    @State private var showError = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header
            Text(isSignUp ? "Create Account" : "Sign In")
                .font(.system(size: 28, weight: .bold))
                .foregroundColor(.black)
            
            Rectangle()
                .fill(Color(hex: "DEE2E6"))
                .frame(height: 1)
                .padding(.top, 12)
                .padding(.bottom, 32)
            
            VStack(alignment: .leading, spacing: 24) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Email")
                        .font(.system(size: 16, weight: .medium))
                        .foregroundColor(.black)
                    TextField("", text: $email)
                        .textFieldStyle(.plain)
                        .padding()
                        .background(Color(hex: "F8F9FA"))
                        .overlay(
                            RoundedRectangle(cornerRadius: 6)
                                .stroke(Color(hex: "ADB5BD"), lineWidth: 1)
                        )
                        .autocapitalization(.none)
                        .keyboardType(.emailAddress)
                        .disabled(firebaseAuth.isAuthenticating)
                }
                
                VStack(alignment: .leading, spacing: 8) {
                    Text("Password")
                        .font(.system(size: 16, weight: .medium))
                        .foregroundColor(.black)
                    SecureField("", text: $password)
                        .textFieldStyle(.plain)
                        .padding()
                        .background(Color(hex: "F8F9FA"))
                        .overlay(
                            RoundedRectangle(cornerRadius: 6)
                                .stroke(Color(hex: "ADB5BD"), lineWidth: 1)
                        )
                        .disabled(firebaseAuth.isAuthenticating)
                }
            }
            .padding(.bottom, 24)
            
            // Error message
            if let error = firebaseAuth.errorMessage {
                Text(error)
                    .font(.system(size: 14, weight: .regular))
                    .foregroundColor(.red)
                    .padding(12)
                    .background(Color(hex: "FFE5E5"))
                    .cornerRadius(6)
                    .padding(.bottom, 24)
            }
            
            Spacer()
            
            Button(action: {
                Task {
                    if isSignUp {
                        await firebaseAuth.signUpWithEmail(email, password: password)
                    } else {
                        await firebaseAuth.signInWithEmail(email, password: password)
                    }
                }
            }) {
                if firebaseAuth.isAuthenticating {
                    ProgressView()
                        .tint(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                        .background(Color(hex: "286EF1").opacity(0.7))
                        .clipShape(RoundedRectangle(cornerRadius: 25))
                } else {
                    Text(isSignUp ? "Create Account" : "Sign In")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                        .background(Color(hex: "286EF1"))
                        .clipShape(RoundedRectangle(cornerRadius: 25))
                }
            }
            .disabled(firebaseAuth.isAuthenticating || email.isEmpty || password.isEmpty)
            
            // Toggle sign up / sign in
            HStack(spacing: 4) {
                Text(isSignUp ? "Have an account?" : "No account?")
                    .foregroundColor(.gray)
                Button(action: { isSignUp.toggle(); firebaseAuth.errorMessage = nil }) {
                    Text(isSignUp ? "Sign In" : "Create one")
                        .foregroundColor(Color(hex: "286EF1"))
                        .font(.system(size: 14, weight: .semibold))
                }
            }
            .frame(maxWidth: .infinity, alignment: .center)
            .padding(.top, 16)
            
            // Anonymous sign in option
            Button(action: {
                Task {
                    await firebaseAuth.signInAnonymously()
                }
            }) {
                Text("Continue as Guest")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(Color(hex: "286EF1"))
            }
            .frame(maxWidth: .infinity)
            .padding(.top, 12)
        }
        .padding(24)
        .background(Color.white)
    }
}

import SwiftUI

struct LoginView: View {
    @State private var email = ""
    @State private var password = ""
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
            
            Text("Login / Sign Up")
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
                }
            }
            .padding(.bottom, 32)
            
            Spacer()
            
            NavigationLink(destination: UploadView()) {
                Text("Start")
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

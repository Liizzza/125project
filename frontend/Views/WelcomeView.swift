import SwiftUI

struct WelcomeView: View {
    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                Circle()
                    .fill(Color(hex: "E0EDFE"))
                    .overlay(Circle().stroke(Color.black, lineWidth: 2))
                    .frame(width: 120, height: 120)
                    .padding(.top, 40)
                    .padding(.bottom, 24)

                Text("Sleep Optimized")
                    .font(.system(size: 28, weight: .bold))
                    .foregroundColor(.black)

                Text("A personalized sleep schedule recommendation system")
                    .font(.system(size: 16, weight: .regular))
                    .foregroundColor(Color(hex: "6C757D"))
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
                    .padding(.top, 8)
                    .padding(.bottom, 40)

                VStack(alignment: .leading, spacing: 24) {
                    FeatureRow(icon: "calendar", title: "Input Your Schedule",
                               description: "Share your daily routine and commitments")
                    FeatureRow(icon: "heart.fill", title: "Add Your Preferences",
                               description: "Choose your preferences based on your real life")
                    FeatureRow(icon: "alarm", title: "Get Personalized Plan",
                               description: "Receive optimized sleep schedule recommendations")
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 40)

                NavigationLink(destination: LoginView()) {
                    Text("Login / Sign Up")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                        .background(Color(hex: "286EF1"))
                        .clipShape(Capsule())
                }
                .padding(.horizontal, 32)
            }
        }
        .background(Color.white)
        .navigationBarHidden(true)
    }
}

struct FeatureRow: View {
    let icon: String
    let title: String
    let description: String

    var body: some View {
        HStack(alignment: .top, spacing: 16) {
            Image(systemName: icon)
                .font(.system(size: 20))
                .foregroundColor(Color(hex: "6C757D"))
                .frame(width: 48, height: 48)
                .background(Color(hex: "F8F0FF"))
                .clipShape(Circle())
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.system(size: 16, weight: .medium))
                    .foregroundColor(.black)
                Text(description)
                    .font(.system(size: 14, weight: .regular))
                    .foregroundColor(Color(hex: "6C757D"))
            }
            Spacer()
        }
    }
}

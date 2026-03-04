import SwiftUI

struct PreferencesView: View {
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
            
            Text("Your Preferences")
                .font(.system(size: 28, weight: .bold))
                .foregroundColor(.black)
            
            Text("Step 2 of 2")
                .font(.system(size: 14, weight: .regular))
                .foregroundColor(Color(hex: "6C757D"))
                .padding(.top, 4)
            
            Rectangle()
                .fill(Color(hex: "DEE2E6"))
                .frame(height: 1)
                .padding(.top, 12)
                .padding(.bottom, 24)
            
            VStack(alignment: .leading, spacing: 16) {
                Text("Gather all other inputs needed...to be determined")
                    .font(.system(size: 16))
                    .foregroundColor(.black)
                
                VStack(alignment: .leading, spacing: 8) {
                    Text("maybe ask")
                    Text("if they are on electronics before bed")
                    Text("how many hours they want to try and aim for")
                    Text("did they drink caffeine that day idkkk")
                }
                .font(.system(size: 16))
                .foregroundColor(.black)
            }
            .padding(.bottom, 32)
            
            Spacer()
            
            NavigationLink(destination: DashboardView()) {
                Text("Generate Sleep Plan")
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

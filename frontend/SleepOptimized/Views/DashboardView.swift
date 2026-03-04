import SwiftUI

struct DashboardView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                // Header
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Sleep Optimized")
                            .font(.system(size: 28, weight: .bold))
                            .foregroundColor(Color(hex: "2D3748"))
                        Text("Monday, Feb 1")
                            .font(.system(size: 14))
                            .foregroundColor(Color(hex: "6C757D"))
                    }
                    Spacer()
                    Circle()
                        .fill(Color(hex: "E0EDFE"))
                        .overlay(Circle().stroke(Color(hex: "286EF1"), lineWidth: 2))
                        .frame(width: 48, height: 48)
                }
                .padding(.bottom, 16)
                
                Text("Score: 4.254")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(.white)
                    .padding(.horizontal, 20)
                    .padding(.vertical, 10)
                    .background(
                        LinearGradient(
                            colors: [Color(hex: "F59E0B"), Color(hex: "EAB308")],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .clipShape(Capsule())
                    .padding(.bottom, 24)
                
                // Recommended Sleep Plan Card
                VStack(alignment: .leading, spacing: 16) {
                    Text("Recommended Sleep Plan")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(.white)
                    
                    HStack(spacing: 48) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Bedtime")
                                .font(.system(size: 14))
                                .foregroundColor(.white.opacity(0.9))
                            Text("23:00")
                                .font(.system(size: 24, weight: .bold))
                                .foregroundColor(.white)
                        }
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Wake Up")
                                .font(.system(size: 14))
                                .foregroundColor(.white.opacity(0.9))
                            Text("07:00")
                                .font(.system(size: 24, weight: .bold))
                                .foregroundColor(.white)
                        }
                    }
                    
                    HStack(spacing: 12) {
                        RoundedRectangle(cornerRadius: 8)
                            .fill(Color.white.opacity(0.3))
                            .frame(height: 44)
                        RoundedRectangle(cornerRadius: 8)
                            .fill(Color.white.opacity(0.3))
                            .frame(height: 44)
                    }
                }
                .padding(20)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(
                    LinearGradient(
                        colors: [Color(hex: "6366F1"), Color(hex: "8B5CF6")],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .padding(.bottom, 16)
                
                // Score Breakdown Card
                VStack(alignment: .leading, spacing: 12) {
                    Text("Score Breakdown")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(Color(hex: "2D3748"))
                    
                    ScoreMetricRow(name: "Sleep Quality", value: 0.98)
                    ScoreMetricRow(name: "Wake Time", value: 1.0)
                    ScoreMetricRow(name: "Bedtime", value: 0.95)
                }
                .padding(20)
                .background(Color.white)
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .shadow(color: .black.opacity(0.06), radius: 4)
                .padding(.bottom, 16)
                
                // Sleep Timeline Card
                VStack(alignment: .leading, spacing: 16) {
                    Text("Sleep Timeline")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(Color(hex: "2D3748"))
                    
                    TimelineNode(time: "23:00", event: "Start your bedtime routine", label: "Wind Down")
                    TimelineConnector()
                    TimelineNode(time: "Sleep Phase", event: "Deep, restorative sleep", label: "8h")
                    TimelineConnector()
                    TimelineNode(time: "07:00", event: "Start your day refreshed", label: "Wake Up")
                }
                .padding(20)
                .background(Color.white)
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .shadow(color: .black.opacity(0.06), radius: 4)
                .padding(.bottom, 16)
                
                // Alternative Options Card
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Text("Alternative Options")
                            .font(.system(size: 16, weight: .semibold))
                            .foregroundColor(Color(hex: "2D3748"))
                        Spacer()
                        Button("Show All") {}
                            .font(.system(size: 14))
                            .foregroundColor(Color(hex: "286EF1"))
                    }
                    
                    HStack {
                        Text("21:30 - 8:30")
                            .font(.system(size: 15, weight: .medium))
                            .foregroundColor(Color(hex: "2D3748"))
                        Spacer()
                        VStack(alignment: .trailing, spacing: 4) {
                            Text("11h opportunity")
                                .font(.system(size: 12))
                                .foregroundColor(Color(hex: "6C757D"))
                            Text("Score: 4.197")
                                .font(.system(size: 12, weight: .semibold))
                                .foregroundColor(.white)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 4)
                                .background(
                                    LinearGradient(
                                        colors: [Color(hex: "F59E0B"), Color(hex: "EAB308")],
                                        startPoint: .leading,
                                        endPoint: .trailing
                                    )
                                )
                                .clipShape(Capsule())
                        }
                        Image(systemName: "chevron.right")
                            .font(.system(size: 14))
                            .foregroundColor(Color(hex: "2D3748"))
                    }
                    .padding(12)
                    .background(Color(hex: "F8FAFC"))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                    
                    HStack(spacing: 8) {
                        Circle().fill(Color(hex: "2D3748")).frame(width: 8, height: 8)
                        Circle().fill(Color(hex: "E2E8F0")).frame(width: 8, height: 8)
                        Circle().fill(Color(hex: "E2E8F0")).frame(width: 8, height: 8)
                    }
                    .frame(maxWidth: .infinity)
                }
                .padding(20)
                .background(Color.white)
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .shadow(color: .black.opacity(0.06), radius: 4)
                .padding(.bottom, 24)
                
                NavigationLink(destination: UploadView()) {
                    Text("Update Schedule")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                        .background(Color.black)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                }
            }
            .padding(24)
        }
        .background(Color(hex: "E8EEF5"))
        .navigationBarBackButtonHidden(true)
    }
}

struct ScoreMetricRow: View {
    let name: String
    let value: Double
    
    var body: some View {
        HStack(spacing: 12) {
            Text(name)
                .font(.system(size: 14))
                .foregroundColor(Color(hex: "2D3748"))
                .frame(width: 100, alignment: .leading)
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color(hex: "E2E8F0"))
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color(hex: "22C55E"))
                        .frame(width: geo.size.width * value)
                }
            }
            .frame(height: 8)
            Text("\(Int(value * 100))%")
                .font(.system(size: 14))
                .foregroundColor(Color(hex: "2D3748"))
                .frame(width: 40, alignment: .trailing)
        }
    }
}

struct TimelineNode: View {
    let time: String
    let event: String
    let label: String
    
    var body: some View {
        HStack(alignment: .top, spacing: 16) {
            Text(time)
                .font(.system(size: 14, weight: .semibold))
                .foregroundColor(Color(hex: "2D3748"))
                .frame(width: 80, alignment: .leading)
            VStack(alignment: .leading, spacing: 4) {
                Text(event)
                    .font(.system(size: 14))
                    .foregroundColor(Color(hex: "2D3748"))
                Text(label)
                    .font(.system(size: 12))
                    .foregroundColor(Color(hex: "6C757D"))
            }
            Spacer()
        }
    }
}

struct TimelineConnector: View {
    var body: some View {
        Rectangle()
            .fill(Color(hex: "E2E8F0"))
            .frame(width: 2, height: 24)
            .padding(.leading, 40)
    }
}

import SwiftUI

struct DashboardView: View {
    @Environment(SleepAPIManager.self) var api

    @State private var bundle: TonightBundle?
    @State private var isLoading = true
    @State private var errorMessage: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                // Header
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Sleep Optimized")
                            .font(.system(size: 28, weight: .bold))
                            .foregroundColor(Color(hex: "2D3748"))
                        Text(todayString())
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

                if isLoading {
                    ProgressView("Building your sleep plan...")
                        .frame(maxWidth: .infinity)
                        .padding(.top, 60)
                } else if let error = errorMessage {
                    VStack(spacing: 12) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.system(size: 40))
                            .foregroundColor(Color(hex: "F59E0B"))
                        Text(error)
                            .font(.system(size: 14))
                            .foregroundColor(Color(hex: "6C757D"))
                            .multilineTextAlignment(.center)
                        Button("Try Again") { Task { await loadBundle() } }
                            .foregroundColor(Color(hex: "286EF1"))
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.top, 60)
                } else if let bundle = bundle {
                    dashboardContent(bundle: bundle)
                }
            }
            .padding(24)
        }
        .background(Color(hex: "E8EEF5"))
        .navigationBarBackButtonHidden(true)
        .task { await loadBundle() }
    }

    // MARK: - Main content

    @ViewBuilder
    private func dashboardContent(bundle: TonightBundle) -> some View {
        let plan = bundle.plan
        let stages = bundle.stages
        
        // Score badge
        Text("Score: \(plan.score, specifier: "%.3f")")
            .font(.system(size: 14, weight: .semibold))
            .foregroundColor(.white)
            .padding(.horizontal, 20)
            .padding(.vertical, 10)
            .background(
                LinearGradient(colors: [Color(hex: "F59E0B"), Color(hex: "EAB308")],
                               startPoint: .topLeading, endPoint: .bottomTrailing)
            )
            .clipShape(Capsule())
            .padding(.bottom, 24)
        
        // Sleep Plan Card
        VStack(alignment: .leading, spacing: 16) {
            Text("Recommended Sleep Plan")
                .font(.system(size: 16, weight: .semibold))
                .foregroundColor(.white)
            
            HStack(spacing: 48) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Bedtime")
                        .font(.system(size: 14))
                        .foregroundColor(.white.opacity(0.9))
                    Text(plan.bedtimeStr)
                        .font(.system(size: 24, weight: .bold))
                        .foregroundColor(.white)
                }
                VStack(alignment: .leading, spacing: 4) {
                    Text("Wake Up")
                        .font(.system(size: 14))
                        .foregroundColor(.white.opacity(0.9))
                    Text(plan.wakeStr)
                        .font(.system(size: 24, weight: .bold))
                        .foregroundColor(.white)
                }
            }
            
            HStack(spacing: 8) {
                InfoPill(label: "\(plan.sleepOpportunityMin) min sleep")
                if plan.debtMin > 0 {
                    InfoPill(label: "Debt: \(Int(plan.debtMin)) min")
                }
                if let nap = plan.napCreditMin, nap > 0 {
                    InfoPill(label: "Nap credit: \(Int(nap)) min")
                }
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            LinearGradient(colors: [Color(hex: "6366F1"), Color(hex: "8B5CF6")],
                           startPoint: .top, endPoint: .bottom)
        )
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .padding(.bottom, 16)
        
        // Sleep Timeline Card
        VStack(alignment: .leading, spacing: 16) {
            Text("Sleep Timeline")
                .font(.system(size: 16, weight: .semibold))
                .foregroundColor(Color(hex: "2D3748"))
            
            TimelineNode(time: plan.bedtimeStr, event: "Start your bedtime routine", label: "Wind Down")
            TimelineConnector()
            TimelineNode(time: "Sleep Phase", event: "Deep, restorative sleep",
                         label: "\(Int(plan.sleepOpportunityMin / 60))h \(Int(plan.sleepOpportunityMin.truncatingRemainder(dividingBy: 60)))m")
            TimelineNode(time: plan.wakeStr, event: "Start your day refreshed", label: "Wake Up")
        }
        .padding(20)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(color: .black.opacity(0.06), radius: 4)
        .padding(.bottom, 16)
        
        // Stage A Content
        if !stages.stageA.recommendations.isEmpty {
            ContentSection(
                title: "Wind-Down Content",
                subtitle: stages.stageA.label,
                recommendations: stages.stageA.recommendations
            )
            .padding(.bottom, 16)
        }
        
        // Stage B Content
        if !stages.stageB.recommendations.isEmpty {
            ContentSection(
                title: "Right Before Bed",
                subtitle: stages.stageB.label,
                recommendations: stages.stageB.recommendations
            )
            .padding(.bottom, 24)
        }
        
        // Update Preferences button
        NavigationLink(destination: PreferencesView()) {
            Text("Update Preferences")
                .font(.system(size: 16, weight: .semibold))
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 16)
                .background(Color(hex: "286EF1"))
                .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .padding(.bottom, 8)
        
        // Re-run plan button
        Button(action: { Task { await loadBundle() } }) {
            Text("Refresh Plan")
                .font(.system(size: 16, weight: .semibold))
                .foregroundColor(Color(hex: "286EF1"))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 16)
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color(hex: "286EF1"), lineWidth: 1.5)
                )
        }
        .padding(.bottom, 8)
        
        // Reset button
        Button(action: { api.clearUser() }) {
            Text("Reset & Start Over")
                .font(.system(size: 14))
                .foregroundColor(Color(hex: "6C757D"))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color(hex: "DEE2E6"), lineWidth: 1)
                )
        }
        .padding(.bottom, 24)
    }


    // MARK: - Data loading

    private func loadBundle() async {
        isLoading = true
        errorMessage = nil
        do {
            let result = try await api.runAndGetBundle()
            bundle = result
        } catch APIError.serverError(let code, _) where code == 404 {
            // User not found on server — clear and restart
            api.clearUser()
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    private func todayString() -> String {
        let f = DateFormatter()
        f.dateFormat = "EEEE, MMM d"
        return f.string(from: Date())
    }
}

// MARK: - Supporting views

struct InfoPill: View {
    let label: String
    var body: some View {
        Text(label)
            .font(.system(size: 12, weight: .medium))
            .foregroundColor(.white)
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(Color.white.opacity(0.25))
            .clipShape(Capsule())
    }
}

struct ContentSection: View {
    let title: String
    let subtitle: String
    let recommendations: [ContentRecommendation]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(Color(hex: "2D3748"))
                Text(subtitle)
                    .font(.system(size: 12))
                    .foregroundColor(Color(hex: "6C757D"))
            }

            ForEach(recommendations.prefix(3)) { rec in
                Link(destination: URL(string: rec.url) ?? URL(string: "https://youtube.com")!) {
                    HStack(spacing: 12) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(rec.title)
                                .font(.system(size: 14, weight: .medium))
                                .foregroundColor(Color(hex: "2D3748"))
                                .lineLimit(2)
                            Text(rec.explain)
                                .font(.system(size: 12))
                                .foregroundColor(Color(hex: "6C757D"))
                                .lineLimit(2)
                        }
                        Spacer()
                        Image(systemName: "play.circle.fill")
                            .font(.system(size: 28))
                            .foregroundColor(Color(hex: "286EF1"))
                    }
                    .padding(12)
                    .background(Color(hex: "F8FAFC"))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                }
            }
        }
        .padding(20)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(color: .black.opacity(0.06), radius: 4)
    }
}

// MARK: - Timeline views (shared)

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

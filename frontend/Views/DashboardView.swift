import SwiftUI

struct DashboardView: View {
    @Environment(SleepAPIManager.self) var api
    @State private var bundle: TonightBundle?
    @State private var isLoading = false
    @State private var error: String?
    @State private var showNapSheet = false
    @State private var todayNap: NapStatus?
    @State private var showResetConfirm = false

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                headerView

                if isLoading {
                    ProgressView("Building your plan...")
                        .padding(40)
                } else if let plan = bundle?.plan {
                    QualityBanner(plan: plan)
                    sleepPlanCard(plan: plan)
                    NapCard(nap: todayNap) { showNapSheet = true }
                    if let stages = bundle?.stages {
                        timelineCard(stages: stages)
                        contentSection(stages: stages)
                    }
                } else {
                    emptyState
                }

                if let error {
                    Text(error)
                        .font(.system(size: 13))
                        .foregroundColor(.red)
                        .padding()
                }
            }
            .padding(16)
        }
        .background(Color(hex: "F0F4FF"))
        .navigationBarHidden(true)
        .sheet(isPresented: $showNapSheet, onDismiss: {
            Task { await loadBundle() }
        }) {
            NapView()
        }
        .task { await loadBundle() }
    }

    // MARK: - Header

    var headerView: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text("Tonight's Plan")
                    .font(.system(size: 26, weight: .bold))
                    .foregroundColor(Color(hex: "1A1A2E"))
                if let gen = bundle?.plan.generatedAt {
                    Text("Updated \(shortTime(gen))")
                        .font(.system(size: 12))
                        .foregroundColor(Color(hex: "6C757D"))
                }
            }
            Spacer()
            HStack(spacing: 12) {
                NavigationLink(destination: PreferencesView()) {
                    Image(systemName: "slider.horizontal.3")
                        .font(.system(size: 18))
                        .foregroundColor(Color(hex: "286EF1"))
                }
                Button(action: { Task { await loadBundle() } }) {
                    Image(systemName: "arrow.clockwise")
                        .font(.system(size: 18))
                        .foregroundColor(Color(hex: "286EF1"))
                }
                Button(action: { showResetConfirm = true }) {
                    Image(systemName: "person.badge.minus")
                        .font(.system(size: 18))
                        .foregroundColor(Color(hex: "ADB5BD"))
                }
                .alert("Reset & Upload New Data?", isPresented: $showResetConfirm) {
                    Button("Cancel", role: .cancel) { }
                    Button("Reset", role: .destructive) { api.clearUser() }
                } message: {
                    Text("This will clear your current session. You'll need to upload a new Health export to continue.")
                }
            }
        }
    }

    // MARK: - Sleep Plan Card

    func sleepPlanCard(plan: SleepPlan) -> some View {
        VStack(spacing: 0) {
            HStack(spacing: 0) {
                sleepStatBlock(
                    icon: "moon.fill",
                    iconColor: Color(hex: "286EF1"),
                    label: "Bedtime",
                    value: plan.bedtimeStr ?? fmt(plan.bedtimeMin)
                )
                Divider().frame(height: 60)
                sleepStatBlock(
                    icon: "sun.max.fill",
                    iconColor: Color(hex: "F59E0B"),
                    label: "Wake up",
                    value: plan.wakeStr ?? fmt(plan.wakeMin)
                )
                Divider().frame(height: 60)
                sleepStatBlock(
                    icon: "clock.fill",
                    iconColor: Color(hex: "22C55E"),
                    label: "Sleep time",
                    value: durationStr(plan.sleepOpportunityMin)
                )
            }
            .padding(.vertical, 16)

            Divider()

            HStack(spacing: 12) {
                debtPill(plan: plan)
                if let nap = plan.napCreditMin, nap > 0 {
                    pill(text: "Nap: -\(Int(nap))m debt", color: "22C55E")
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
        }
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
    }

    func sleepStatBlock(icon: String, iconColor: Color, label: String, value: String) -> some View {
        VStack(spacing: 4) {
            Image(systemName: icon)
                .font(.system(size: 16))
                .foregroundColor(iconColor)
            Text(value)
                .font(.system(size: 20, weight: .bold))
                .foregroundColor(Color(hex: "1A1A2E"))
            Text(label)
                .font(.system(size: 11))
                .foregroundColor(Color(hex: "6C757D"))
        }
        .frame(maxWidth: .infinity)
    }

    func debtPill(plan: SleepPlan) -> some View {
        let debt = Int(plan.debtMin)
        let color = debt < 60 ? "22C55E" : debt < 300 ? "286EF1" : debt < 600 ? "F59E0B" : "EF4444"
        return pill(text: "Debt: \(debt)m", color: color)
    }

    func pill(text: String, color: String) -> some View {
        Text(text)
            .font(.system(size: 12, weight: .medium))
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(Color(hex: color).opacity(0.12))
            .foregroundColor(Color(hex: color))
            .clipShape(Capsule())
    }

    // MARK: - Timeline Card

    func timelineCard(stages: SleepStages) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Tonight's Timeline")
                .font(.system(size: 15, weight: .semibold))
                .foregroundColor(Color(hex: "1A1A2E"))

            HStack(spacing: 0) {
                timelineStep(icon: "circle.fill", color: "286EF1", label: "Now",
                             time: shortTimeFromISO(stages.nowIso))
                timelineLine()
                timelineStep(icon: "moon.zzz.fill", color: "7C3AED", label: "Stage A",
                             time: "Wind down")
                timelineLine()
                timelineStep(icon: "moon.fill", color: "1A1A2E", label: "Bed",
                             time: fmt(stages.bedtimeMins))
                timelineLine()
                timelineStep(icon: "sun.max.fill", color: "F59E0B", label: "Wake",
                             time: fmt(stages.wakeMins))
            }
        }
        .padding(16)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
    }

    func timelineStep(icon: String, color: String, label: String, time: String) -> some View {
        VStack(spacing: 4) {
            Image(systemName: icon)
                .font(.system(size: 14))
                .foregroundColor(Color(hex: color))
            Text(time)
                .font(.system(size: 12, weight: .semibold))
                .foregroundColor(Color(hex: "1A1A2E"))
            Text(label)
                .font(.system(size: 10))
                .foregroundColor(Color(hex: "6C757D"))
        }
        .frame(maxWidth: .infinity)
    }

    func timelineLine() -> some View {
        Rectangle()
            .fill(Color(hex: "DEE2E6"))
            .frame(height: 1)
            .padding(.bottom, 20)
    }

    // MARK: - Content Section

    func contentSection(stages: SleepStages) -> some View {
        VStack(spacing: 12) {
            if !stages.stageA.recommendations.isEmpty {
                stageCard(title: stages.stageA.label,
                          window: stages.stageA.window ?? "",
                          recs: stages.stageA.recommendations,
                          accentColor: "7C3AED")
            }
            if !stages.stageB.recommendations.isEmpty {
                stageCard(title: stages.stageB.label,
                          window: stages.stageB.window ?? "",
                          recs: stages.stageB.recommendations,
                          accentColor: "286EF1")
            }
        }
    }

    func stageCard(title: String, window: String, recs: [ContentRecommendation], accentColor: String) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundColor(Color(hex: "1A1A2E"))
                    Text(window)
                        .font(.system(size: 11))
                        .foregroundColor(Color(hex: "6C757D"))
                }
                Spacer()
                Text("\(recs.count) videos")
                    .font(.system(size: 11))
                    .foregroundColor(Color(hex: accentColor))
            }

            ForEach(recs.prefix(3), id: \.url) { rec in
                Link(destination: URL(string: rec.url)!) {
                    HStack(spacing: 10) {
                        RoundedRectangle(cornerRadius: 6)
                            .fill(Color(hex: accentColor).opacity(0.12))
                            .frame(width: 36, height: 36)
                            .overlay(
                                Text("\(Int(rec.durationMin))m")
                                    .font(.system(size: 10, weight: .bold))
                                    .foregroundColor(Color(hex: accentColor))
                            )
                        VStack(alignment: .leading, spacing: 2) {
                            Text(rec.title)
                                .font(.system(size: 13, weight: .medium))
                                .foregroundColor(Color(hex: "1A1A2E"))
                                .lineLimit(2)
                            Text(rec.explain)
                                .font(.system(size: 11))
                                .foregroundColor(Color(hex: "6C757D"))
                                .lineLimit(1)
                        }
                        Spacer()
                        Image(systemName: "play.circle.fill")
                            .foregroundColor(Color(hex: accentColor))
                            .font(.system(size: 20))
                    }
                }
            }
        }
        .padding(16)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
    }

    // MARK: - Empty State

    var emptyState: some View {
        VStack(spacing: 16) {
            Image(systemName: "moon.stars.fill")
                .font(.system(size: 48))
                .foregroundColor(Color(hex: "286EF1").opacity(0.4))
            Text("No plan yet")
                .font(.system(size: 18, weight: .semibold))
                .foregroundColor(Color(hex: "1A1A2E"))
            Text("Tap refresh to generate tonight's sleep plan")
                .font(.system(size: 14))
                .foregroundColor(Color(hex: "6C757D"))
                .multilineTextAlignment(.center)
            Button(action: { Task { await loadBundle() } }) {
                Text("Generate Plan")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundColor(.white)
                    .padding(.horizontal, 24)
                    .padding(.vertical, 12)
                    .background(Color(hex: "286EF1"))
                    .clipShape(Capsule())
            }
        }
        .padding(40)
    }

    // MARK: - Load

    private func loadBundle() async {
        isLoading = true
        error = nil
        do {
            bundle = try await api.runAndGetBundle()
        } catch {
            // Try fetching existing bundle if run fails
            if let existing = try? await api.getBundle() {
                bundle = existing
            } else {
                self.error = error.localizedDescription
                if error.localizedDescription.contains("404") { api.clearUser() }
            }
        }
        await loadTodayNap()
        isLoading = false
    }

    private func loadTodayNap() async {
        todayNap = try? await api.getTodayNap()
    }

    // MARK: - Helpers

    private func fmt(_ mins: Double) -> String {
        let m = Int(mins) % 1440
        let h = m / 60, min = m % 60
        let ampm = h < 12 ? "AM" : "PM"
        let h12 = h % 12 == 0 ? 12 : h % 12
        return "\(h12):\(String(format: "%02d", min)) \(ampm)"
    }

    private func durationStr(_ mins: Double) -> String {
        let h = Int(mins) / 60, m = Int(mins) % 60
        return m == 0 ? "\(h)h" : "\(h)h \(m)m"
    }

    private func shortTime(_ iso: String) -> String {
        guard let date = ISO8601DateFormatter().date(from: iso) else { return "" }
        let f = DateFormatter(); f.timeStyle = .short
        return f.string(from: date)
    }

    private func shortTimeFromISO(_ iso: String) -> String { shortTime(iso) }
}

// MARK: - Quality Banner

struct QualityBanner: View {
    let plan: SleepPlan

    var label: String { plan.qualityLabel ?? qualityFromDebt().label }
    var subtitle: String { plan.qualitySubtitle ?? qualityFromDebt().subtitle }
    var color: Color { Color(hex: plan.qualityColor ?? qualityFromDebt().color) }

    var body: some View {
        HStack(spacing: 12) {
            Circle()
                .fill(color.opacity(0.15))
                .frame(width: 44, height: 44)
                .overlay(
                    Image(systemName: qualityIcon)
                        .font(.system(size: 20))
                        .foregroundColor(color)
                )
            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .font(.system(size: 17, weight: .bold))
                    .foregroundColor(Color(hex: "1A1A2E"))
                Text(subtitle)
                    .font(.system(size: 13))
                    .foregroundColor(Color(hex: "6C757D"))
            }
            Spacer()
        }
        .padding(14)
        .background(color.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .overlay(
            RoundedRectangle(cornerRadius: 14)
                .stroke(color.opacity(0.25), lineWidth: 1)
        )
    }

    private var qualityIcon: String {
        switch label {
        case "Well Rested":     return "star.fill"
        case "On Track":        return "checkmark.circle.fill"
        case "Recovering":      return "arrow.up.heart.fill"
        case "Slightly Behind": return "clock.badge.exclamationmark.fill"
        case "Catch-Up Needed": return "exclamationmark.triangle.fill"
        case "High Debt":       return "bed.double.fill"
        default:                return "moon.fill"
        }
    }

    // Fallback if server doesn't return quality fields yet
    private func qualityFromDebt() -> (label: String, subtitle: String, color: String) {
        let debt = plan.debtMin
        if debt < 60      { return ("Well Rested",     "Your sleep is on track",             "22C55E") }
        if debt < 300     { return ("Recovering",       "Good plan to catch up",               "286EF1") }
        if debt < 600     { return ("Catch-Up Needed",  "Prioritize sleep this week",          "F59E0B") }
        return               ("High Debt",          "Focus on consistent early bedtimes",  "EF4444")
    }
}

// MARK: - Nap Card

struct NapCard: View {
    let nap: NapStatus?
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 12) {
                Image(systemName: nap?.hasNap == true ? "moon.zzz.fill" : "moon.zzz")
                    .font(.system(size: 22))
                    .foregroundColor(Color(hex: "7C3AED"))
                    .frame(width: 44, height: 44)
                    .background(Color(hex: "7C3AED").opacity(0.1))
                    .clipShape(Circle())

                VStack(alignment: .leading, spacing: 2) {
                    Text(nap?.hasNap == true ? "Nap logged" : "Log a nap")
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundColor(Color(hex: "1A1A2E"))
                    if let dur = nap?.durationMinutes {
                        Text("\(dur) min · reduces tonight's debt")
                            .font(.system(size: 12))
                            .foregroundColor(Color(hex: "6C757D"))
                    } else {
                        Text("Naps count toward your sleep debt")
                            .font(.system(size: 12))
                            .foregroundColor(Color(hex: "6C757D"))
                    }
                }
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.system(size: 13))
                    .foregroundColor(Color(hex: "ADB5BD"))
            }
            .padding(14)
            .background(Color.white)
            .clipShape(RoundedRectangle(cornerRadius: 14))
            .shadow(color: .black.opacity(0.05), radius: 6, x: 0, y: 2)
        }
    }
}

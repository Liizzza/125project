import SwiftUI

// MARK: - Main View
struct PreferencesView: View {
    @EnvironmentObject var api: SleepAPIManager
    @Environment(\.dismiss) private var dismiss

    @State private var targetSleepHours: Double = 8.0
    @State private var preferredWakeTime: Date = Calendar.current.date(bySettingHour: 7, minute: 30, second: 0, of: Date()) ?? Date()
    @State private var mustWakeBy: Date = Calendar.current.date(bySettingHour: 8, minute: 0, second: 0, of: Date()) ?? Date()
    @State private var noBedAfter: Date = Calendar.current.date(bySettingHour: 23, minute: 30, second: 0, of: Date()) ?? Date()
    @State private var hadCaffeineToday: Bool = false
    @State private var caffeineCutoffTime: Date = Calendar.current.date(bySettingHour: 14, minute: 0, second: 0, of: Date()) ?? Date()
    @State private var avoidHighIntensityNearBed: Bool = true
    @State private var selectedStageACategories: Set<String> = ["nature", "stories"]
    @State private var selectedStageBCategories: Set<String> = ["meditation", "noise"]
    @State private var isSaving = false
    @State private var saveError: String?
    @State private var navigateToDashboard = false

    let allCategories = ["noise", "nature", "meditation", "asmr", "stories", "music", "gentle_movement"]

    var body: some View {
        NavigationStack {
            Group {
                if !api.isEmailVerified {
                    VStack(spacing: 24) {
                        Image(systemName: "envelope.badge")
                            .font(.system(size: 48))
                            .foregroundColor(Color(hex: "286EF1"))
                        Text("Please verify your email to set preferences.")
                            .font(.system(size: 18, weight: .semibold))
                            .multilineTextAlignment(.center)
                        Button("Resend Verification Email") {
                            api.sendEmailVerification { error in
                                if let error = error { print("Error: \(error.localizedDescription)") }
                            }
                        }
                    }
                    .padding(40)
                } else {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 0) {
                            Button(action: { dismiss() }) {
                                Image(systemName: "chevron.left")
                                    .font(.system(size: 24, weight: .medium))
                                    .foregroundColor(Color(hex: "286EF1"))
                            }
                            .padding(.bottom, 8)

                            Text("Your Preferences").font(.system(size: 28, weight: .bold))
                            Text("Step 2 of 2").font(.system(size: 14)).foregroundColor(.gray)

                            Divider().padding(.vertical, 20)

                            SectionHeader(title: "Sleep Goals")
                            VStack(alignment: .leading) {
                                HStack {
                                    Text("Target sleep")
                                    Spacer()
                                    Text("\(targetSleepHours, specifier: "%.1f") hrs").bold()
                                }
                                Slider(value: $targetSleepHours, in: 5...10, step: 0.5)
                            }
                            .preferenceCard()

                            SectionHeader(title: "Schedule").padding(.top, 20)
                            VStack(spacing: 0) {
                                TimePickerRow(label: "Preferred wake", time: $preferredWakeTime)
                                Divider()
                                TimePickerRow(label: "Must wake by", time: $mustWakeBy)
                            }
                            .preferenceCard()

                            SectionHeader(title: "Wind-Down Content").padding(.top, 20)
                            VStack(alignment: .leading, spacing: 12) {
                                Text("Stage A (Evening)").font(.caption).bold()
                                CategoryPicker(selected: $selectedStageACategories, categories: allCategories)
                                Text("Stage B (Bedtime)").font(.caption).bold()
                                CategoryPicker(selected: $selectedStageBCategories, categories: allCategories)
                            }
                            .preferenceCard()
                            .padding(.bottom, 30)

                            if let error = saveError {
                                Text(error).foregroundColor(.red).font(.caption).padding(.bottom, 10)
                            }

                            Button(action: handleGenerate) {
                                if isSaving { ProgressView().tint(.white) }
                                else { Text("Save & Update Plan").bold() }
                            }
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(isSaving ? Color.gray : Color(hex: "286EF1"))
                            .foregroundColor(.white)
                            .clipShape(Capsule())
                            .disabled(isSaving)
                        }
                        .padding(24)
                    }
                }
            }
            .navigationDestination(isPresented: $navigateToDashboard) {
                DashboardView().navigationBarBackButtonHidden(true)
            }
        }
    }

    func handleGenerate() {
        isSaving = true
        let prefs = SleepPreferencesRequest(
            targetSleepHours: targetSleepHours,
            mustWakeBy: timeString(from: mustWakeBy),
            preferredWakeTime: timeString(from: preferredWakeTime),
            noBedAfter: timeString(from: noBedAfter),
            avoidHighIntensityNearBed: avoidHighIntensityNearBed,
            stageACategories: Array(selectedStageACategories),
            stageBCategories: Array(selectedStageBCategories)
        )

        Task {
            do {
                try await api.savePreferences(prefs)
                try await api.runAndGetBundle()
                _ = try await api.getBundleWithRetry()
                await MainActor.run {
                    navigateToDashboard = true
                    isSaving = false
                }
            } catch {
                await MainActor.run {
                    saveError = "Update failed. Try again."
                    isSaving = false
                }
            }
        }
    }

    func timeString(from date: Date) -> String {
        let f = DateFormatter(); f.dateFormat = "HH:mm"; return f.string(from: date)
    }
}

// MARK: - Sub-Components (All required for build)

struct SectionHeader: View {
    let title: String
    var body: some View {
        Text(title).font(.system(size: 13, weight: .semibold)).foregroundColor(.gray).textCase(.uppercase)
    }
}

struct TimePickerRow: View {
    let label: String
    @Binding var time: Date
    var body: some View {
        HStack {
            Text(label).font(.system(size: 15))
            Spacer()
            DatePicker("", selection: $time, displayedComponents: .hourAndMinute).labelsHidden()
        }.padding(.vertical, 8).padding(.horizontal, 12)
    }
}

struct CategoryPicker: View {
    @Binding var selected: Set<String>
    let categories: [String]
    var body: some View {
        FlowLayout(spacing: 8) {
            ForEach(categories, id: \.self) { cat in
                Button(action: {
                    if selected.contains(cat) { selected.remove(cat) }
                    else { selected.insert(cat) }
                }) {
                    Text(cat.replacingOccurrences(of: "_", with: " "))
                        .font(.caption).padding(.horizontal, 10).padding(.vertical, 5)
                        .background(selected.contains(cat) ? Color.blue : Color(.systemGray6))
                        .foregroundColor(selected.contains(cat) ? .white : .blue)
                        .clipShape(Capsule())
                }
            }
        }
    }
}

struct FlowLayout: Layout {
    var spacing: CGFloat = 8
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? 0
        var x: CGFloat = 0, y: CGFloat = 0, maxHeight: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x + size.width > width { x = 0; y += maxHeight + spacing; maxHeight = 0 }
            x += size.width + spacing
            maxHeight = max(maxHeight, size.height)
        }
        return CGSize(width: width, height: y + maxHeight)
    }
    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, maxHeight: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x + size.width > bounds.maxX { x = bounds.minX; y += maxHeight + spacing; maxHeight = 0 }
            view.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(size))
            x += size.width + spacing
            maxHeight = max(maxHeight, size.height)
        }
    }
}

extension View {
    func preferenceCard() -> some View {
        self.padding(16).background(Color(.systemGray6)).clipShape(RoundedRectangle(cornerRadius: 12))
    }
}



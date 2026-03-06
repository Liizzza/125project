import SwiftUI

struct PreferencesView: View {
    @EnvironmentObject var api: SleepAPIManager
    @Environment(\.dismiss) private var dismiss

    // Schedule
    @State private var targetSleepHours: Double = 8.0
    @State private var preferredWakeTime: Date = Calendar.current.date(
        bySettingHour: 7, minute: 30, second: 0, of: Date()) ?? Date()
    @State private var mustWakeBy: Date = Calendar.current.date(
        bySettingHour: 8, minute: 0, second: 0, of: Date()) ?? Date()
    @State private var noBedAfter: Date = Calendar.current.date(
        bySettingHour: 23, minute: 30, second: 0, of: Date()) ?? Date()

    // Habits
    @State private var hadCaffeineToday: Bool = false
    @State private var caffeineCutoffTime: Date = Calendar.current.date(
        bySettingHour: 14, minute: 0, second: 0, of: Date()) ?? Date()
    @State private var avoidHighIntensityNearBed: Bool = true

    // Content preferences
    @State private var selectedStageACategories: Set<String> = ["nature", "stories"]
    @State private var selectedStageBCategories: Set<String> = ["meditation", "noise"]

    // State
    @State private var isSaving = false
    @State private var saveError: String?
    @State private var navigateToDashboard = false

    let allCategories = ["noise", "nature", "meditation", "asmr", "stories", "music", "gentle_movement"]

    var body: some View {
        ScrollView {
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
                    .font(.system(size: 14))
                    .foregroundColor(Color(hex: "6C757D"))
                    .padding(.top, 4)

                Rectangle()
                    .fill(Color(hex: "DEE2E6"))
                    .frame(height: 1)
                    .padding(.top, 12)
                    .padding(.bottom, 24)

                // ── Sleep Goals ────────────────────────────────────────────────
                SectionHeader(title: "Sleep Goals")

                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("Target sleep duration")
                            .font(.system(size: 15))
                            .foregroundColor(Color(hex: "2D3748"))
                        Spacer()
                        Text("\(targetSleepHours, specifier: "%.1f") hrs")
                            .font(.system(size: 15, weight: .semibold))
                            .foregroundColor(Color(hex: "286EF1"))
                    }
                    Slider(value: $targetSleepHours, in: 5...10, step: 0.5)
                        .tint(Color(hex: "286EF1"))
                }
                .preferenceCard()
                .padding(.bottom, 12)

                // ── Schedule ───────────────────────────────────────────────────
                SectionHeader(title: "Schedule")

                VStack(spacing: 0) {
                    TimePickerRow(label: "Preferred wake time", time: $preferredWakeTime)
                    Divider().padding(.horizontal)
                    TimePickerRow(label: "Must be awake by", time: $mustWakeBy)
                    Divider().padding(.horizontal)
                    TimePickerRow(label: "No bed after", time: $noBedAfter)
                }
                .preferenceCard()
                .padding(.bottom, 12)

                // ── Evening Habits ─────────────────────────────────────────────
                SectionHeader(title: "Evening Habits")

                VStack(spacing: 0) {
                    ToggleRow(
                        label: "Had caffeine today?",
                        sublabel: "Helps us avoid recommending bed too soon after caffeine",
                        isOn: $hadCaffeineToday
                    )
                    if hadCaffeineToday {
                        Divider().padding(.horizontal)
                        TimePickerRow(label: "Last caffeine at", time: $caffeineCutoffTime)
                    }
                    Divider().padding(.horizontal)
                    ToggleRow(
                        label: "Avoid stimulating content near bed",
                        sublabel: "We'll show calmer content as bedtime approaches",
                        isOn: $avoidHighIntensityNearBed
                    )
                }
                .preferenceCard()
                .padding(.bottom, 12)

                // ── Wind-Down Content ──────────────────────────────────────────
                SectionHeader(title: "Wind-Down Content")

                VStack(alignment: .leading, spacing: 12) {
                    Text("Earlier in the evening (Stage A)")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(Color(hex: "2D3748"))
                    CategoryPicker(selected: $selectedStageACategories, categories: allCategories)

                    Text("Close to bedtime (Stage B)")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(Color(hex: "2D3748"))
                        .padding(.top, 4)
                    CategoryPicker(selected: $selectedStageBCategories, categories: allCategories)
                }
                .preferenceCard()
                .padding(.bottom, 32)

                if let error = saveError {
                    Text(error)
                        .font(.system(size: 13))
                        .foregroundColor(.red)
                        .padding(.bottom, 8)
                }

                // ── Generate Button ────────────────────────────────────────────
                Button(action: handleGenerate) {
                    HStack(spacing: 8) {
                        if isSaving { ProgressView().tint(.white) }
                        Text(isSaving ? "Generating..." : "Generate Sleep Plan")
                            .font(.system(size: 16, weight: .semibold))
                            .foregroundColor(.white)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
                    .background(isSaving ? Color(hex: "ADB5BD") : Color(hex: "286EF1"))
                    .clipShape(RoundedRectangle(cornerRadius: 25))
                }
                .disabled(isSaving)

                NavigationLink(destination: DashboardView(), isActive: $navigateToDashboard) {
                    EmptyView()
                }
            }
            .padding(24)
        }
        .background(Color.white)
        .navigationBarBackButtonHidden(true)
    }

    private func handleGenerate() {
        isSaving = true
        saveError = nil

        let prefs = SleepPreferencesRequest(
            targetSleepHours: targetSleepHours,
            mustWakeBy: timeString(from: mustWakeBy),
            preferredWakeTime: timeString(from: preferredWakeTime),
            noBedAfter: timeString(from: noBedAfter),
            avoidHighIntensityNearBed: avoidHighIntensityNearBed,
            caffeineCutoffTime: hadCaffeineToday ? timeString(from: caffeineCutoffTime) : nil,
            stageACategories: Array(selectedStageACategories),
            stageBCategories: Array(selectedStageBCategories)
        )

        Task {
            do {
                try await api.savePreferences(prefs)
                navigateToDashboard = true
            } catch {
                saveError = error.localizedDescription
            }
            isSaving = false
        }
    }

    private func timeString(from date: Date) -> String {
        let f = DateFormatter()
        f.dateFormat = "HH:mm"
        return f.string(from: date)
    }
}

// MARK: - Sub-components

struct SectionHeader: View {
    let title: String
    var body: some View {
        Text(title)
            .font(.system(size: 13, weight: .semibold))
            .foregroundColor(Color(hex: "6C757D"))
            .textCase(.uppercase)
            .padding(.bottom, 8)
    }
}

struct TimePickerRow: View {
    let label: String
    @Binding var time: Date

    var body: some View {
        HStack {
            Text(label)
                .font(.system(size: 15))
                .foregroundColor(Color(hex: "2D3748"))
            Spacer()
            DatePicker("", selection: $time, displayedComponents: .hourAndMinute)
                .labelsHidden()
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }
}

struct ToggleRow: View {
    let label: String
    let sublabel: String
    @Binding var isOn: Bool

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .font(.system(size: 15))
                    .foregroundColor(Color(hex: "2D3748"))
                Text(sublabel)
                    .font(.system(size: 12))
                    .foregroundColor(Color(hex: "6C757D"))
            }
            Spacer()
            Toggle("", isOn: $isOn)
                .tint(Color(hex: "286EF1"))
                .labelsHidden()
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
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
                        .font(.system(size: 13, weight: .medium))
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(selected.contains(cat)
                            ? Color(hex: "286EF1")
                            : Color(hex: "F0F4FF"))
                        .foregroundColor(selected.contains(cat) ? .white : Color(hex: "286EF1"))
                        .clipShape(Capsule())
                }
            }
        }
    }
}

// Simple flow layout for wrapping chips
struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? 0
        var x: CGFloat = 0, y: CGFloat = 0, maxHeight: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x + size.width > width {
                x = 0; y += maxHeight + spacing; maxHeight = 0
            }
            x += size.width + spacing
            maxHeight = max(maxHeight, size.height)
        }
        return CGSize(width: width, height: y + maxHeight)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, maxHeight: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x + size.width > bounds.maxX {
                x = bounds.minX; y += maxHeight + spacing; maxHeight = 0
            }
            view.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(size))
            x += size.width + spacing
            maxHeight = max(maxHeight, size.height)
        }
    }
}

extension View {
    func preferenceCard() -> some View {
        self
            .padding(16)
            .background(Color(hex: "F8F9FA"))
            .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}
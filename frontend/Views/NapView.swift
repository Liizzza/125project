//
//  NapView.swift
//  SleepOptimized
//
//  Created by liza shchehlik on 3/9/26.
//

import SwiftUI

struct NapView: View {
    @Environment(SleepAPIManager.self) var api
    @Environment(\.dismiss) private var dismiss

    @State private var durationMinutes: Double = 20
    @State private var includeTime: Bool = false
    @State private var napTime: Date = Calendar.current.date(
        bySettingHour: 14, minute: 0, second: 0, of: Date()) ?? Date()

    @State private var isSaving = false
    @State private var saveError: String?
    @State private var savedNap: NapResponse?

    // Quick pick presets
    let presets = [10, 20, 30, 45, 60, 90]

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Handle bar
            RoundedRectangle(cornerRadius: 3)
                .fill(Color(hex: "DEE2E6"))
                .frame(width: 40, height: 5)
                .frame(maxWidth: .infinity)
                .padding(.top, 12)
                .padding(.bottom, 20)

            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    Text("Log a Nap")
                        .font(.system(size: 24, weight: .bold))
                        .foregroundColor(Color(hex: "2D3748"))

                    Text("Naps count toward your sleep debt — we'll adjust tonight's plan.")
                        .font(.system(size: 14))
                        .foregroundColor(Color(hex: "6C757D"))
                        .padding(.top, 4)
                        .padding(.bottom, 24)

                    if let saved = savedNap {
                        // Success state
                        VStack(spacing: 16) {
                            Image(systemName: "checkmark.circle.fill")
                                .font(.system(size: 48))
                                .foregroundColor(Color(hex: "22C55E"))

                            Text("Nap logged!")
                                .font(.system(size: 20, weight: .semibold))
                                .foregroundColor(Color(hex: "2D3748"))

                            VStack(spacing: 8) {
                                HStack {
                                    Text("Duration")
                                        .foregroundColor(Color(hex: "6C757D"))
                                    Spacer()
                                    Text("\(Int(saved.nap?.durationMinutes ?? 0)) min")
                                        .fontWeight(.semibold)
                                }
                                if let dur = saved.nap?.durationMinutes {
                                    HStack {
                                        Text("Sleep debt reduced by")
                                            .foregroundColor(Color(hex: "6C757D"))
                                        Spacer()
                                        Text("\(Int(dur)) min")
                                            .fontWeight(.semibold)
                                            .foregroundColor(Color(hex: "22C55E"))
                                    }
                                }                            }
                            .padding(16)
                            .background(Color(hex: "F8F9FA"))
                            .clipShape(RoundedRectangle(cornerRadius: 12))

                            Text("Refresh your sleep plan on the dashboard to see the updated bedtime.")
                                .font(.system(size: 13))
                                .foregroundColor(Color(hex: "6C757D"))
                                .multilineTextAlignment(.center)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)

                    } else {
                        // Input state

                        // Duration slider
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Text("Duration")
                                    .font(.system(size: 13, weight: .semibold))
                                    .foregroundColor(Color(hex: "6C757D"))
                                    .textCase(.uppercase)
                                Spacer()
                                Text("\(Int(durationMinutes)) min")
                                    .font(.system(size: 16, weight: .semibold))
                                    .foregroundColor(Color(hex: "286EF1"))
                            }

                            Slider(value: $durationMinutes, in: 5...120, step: 5)
                                .tint(Color(hex: "286EF1"))

                            // Quick presets
                            HStack(spacing: 8) {
                                ForEach(presets, id: \.self) { p in
                                    Button(action: { durationMinutes = Double(p) }) {
                                        Text("\(p)m")
                                            .font(.system(size: 13, weight: .medium))
                                            .padding(.horizontal, 10)
                                            .padding(.vertical, 6)
                                            .background(Int(durationMinutes) == p
                                                ? Color(hex: "286EF1")
                                                : Color(hex: "F0F4FF"))
                                            .foregroundColor(Int(durationMinutes) == p
                                                ? .white
                                                : Color(hex: "286EF1"))
                                            .clipShape(Capsule())
                                    }
                                }
                            }
                        }
                        .padding(16)
                        .background(Color(hex: "F8F9FA"))
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                        .padding(.bottom, 12)

                        // Optional time
                        VStack(spacing: 0) {
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("Add nap time")
                                        .font(.system(size: 15))
                                        .foregroundColor(Color(hex: "2D3748"))
                                    Text("Optional — helps with timing analysis")
                                        .font(.system(size: 12))
                                        .foregroundColor(Color(hex: "6C757D"))
                                }
                                Spacer()
                                Toggle("", isOn: $includeTime)
                                    .tint(Color(hex: "286EF1"))
                                    .labelsHidden()
                            }
                            .padding(16)

                            if includeTime {
                                Divider().padding(.horizontal)
                                HStack {
                                    Text("Nap started at")
                                        .font(.system(size: 15))
                                        .foregroundColor(Color(hex: "2D3748"))
                                    Spacer()
                                    DatePicker("", selection: $napTime, displayedComponents: .hourAndMinute)
                                        .labelsHidden()
                                }
                                .padding(16)
                            }
                        }
                        .background(Color(hex: "F8F9FA"))
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                        .padding(.bottom, 24)

                        if let error = saveError {
                            Text(error)
                                .font(.system(size: 13))
                                .foregroundColor(.red)
                                .padding(.bottom, 8)
                        }

                        Button(action: handleSave) {
                            HStack(spacing: 8) {
                                if isSaving { ProgressView().tint(.white) }
                                Text(isSaving ? "Logging..." : "Log Nap")
                                    .font(.system(size: 16, weight: .semibold))
                                    .foregroundColor(.white)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 16)
                            .background(isSaving ? Color(hex: "ADB5BD") : Color(hex: "286EF1"))
                            .clipShape(RoundedRectangle(cornerRadius: 25))
                        }
                        .disabled(isSaving)
                    }

                    // Done button always visible after save
                    if savedNap != nil {
                        Button(action: { dismiss() }) {
                            Text("Done")
                                .font(.system(size: 16, weight: .semibold))
                                .foregroundColor(Color(hex: "286EF1"))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 16)
                                .overlay(
                                    RoundedRectangle(cornerRadius: 25)
                                        .stroke(Color(hex: "286EF1"), lineWidth: 1.5)
                                )
                        }
                        .padding(.top, 12)
                    }
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 40)
            }
        }
        .background(Color.white)
    }

    private func handleSave() {
        isSaving = true
        saveError = nil
        let timeStr: String? = includeTime ? {
            let f = DateFormatter()
            f.dateFormat = "HH:mm"
            return f.string(from: napTime)
        }() : nil

        Task {
            do {
                let result = try await api.logNap(durationMinutes: Int(durationMinutes), napTime: timeStr)
                savedNap = result
            } catch {
                saveError = error.localizedDescription
            }
            isSaving = false
        }
    }
}

import Foundation

// ─────────────────────────────────────────────────────────────────────────────
// SleepAPIManager.swift  (multi-user version)
//
// How it works:
//   1. User uploads their export.xml → server returns a user_id (UUID)
//   2. user_id is saved to UserDefaults automatically
//   3. All future API calls include the user_id in the URL path
//   4. If the app is reinstalled / user_id is lost, just upload again
// ─────────────────────────────────────────────────────────────────────────────

// MARK: - Response Models

struct UploadResponse: Codable {
    let userId: String
    let message: String
    let nextStep: String

    enum CodingKeys: String, CodingKey {
        case userId   = "user_id"
        case message
        case nextStep = "next_step"
    }
}

struct SleepPlan: Codable {
    let generatedAt: String
    let bedtimeMin: Int
    let wakeMin: Int
    let bedtimeStr: String
    let wakeStr: String
    let sleepOpportunityMin: Int
    let desiredSleepMin: Int
    let debtMin: Double
    let score: Double
    let napCreditMin: Double?

    enum CodingKeys: String, CodingKey {
        case generatedAt         = "generated_at"
        case bedtimeMin          = "bedtime_min"
        case wakeMin             = "wake_min"
        case bedtimeStr          = "bedtime_str"
        case wakeStr             = "wake_str"
        case sleepOpportunityMin = "sleep_opportunity_min"
        case desiredSleepMin     = "desired_sleep_min"
        case debtMin             = "debt_min"
        case score
        case napCreditMin = "nap_credit_min"
    }
}

struct ContentRecommendation: Codable, Identifiable {
    var id: Int { rank }
    let rank: Int
    let score: Double
    let title: String
    let url: String
    let category: String
    let durationMin: Double
    let intensity: Double
    let explain: String

    enum CodingKeys: String, CodingKey {
        case rank, score, title, url, category, intensity, explain
        case durationMin = "durationMin"
    }
}

struct ContentResponse: Codable {
    let userId: String?
    let generatedAt: String?
    let recommendations: [ContentRecommendation]

    enum CodingKeys: String, CodingKey {
        case userId      = "user_id"
        case generatedAt = "generated_at"
        case recommendations
    }
}

struct SleepPreferencesRequest: Codable {
    var targetSleepHours: Double        = 8.0
    var mustWakeBy: String?
    var preferredWakeTime: String?
    var noBedAfter: String?
    var minSleepOpportunityHours: Double?
    var avoidHighIntensityNearBed: Bool = false
    var caffeineCutoffTime: String?
    var preferredCategories: [String]?

    /// Override default category weights. Only specify what you want to change.
    /// Keys: noise, nature, meditation, asmr, stories, music, gentle_movement, other
    /// Values: 0.0–2.0 (higher = shown more often). Default range is 0.85–1.15.
    var categoryWeights: [String: Double]? = nil
    var stageACategories: [String]? = nil
    var stageBCategories: [String]? = nil

    enum CodingKeys: String, CodingKey {
        case targetSleepHours          = "target_sleep_hours"
        case mustWakeBy                = "must_wake_by"
        case preferredWakeTime         = "preferred_wake_time"
        case noBedAfter                = "no_bed_after"
        case minSleepOpportunityHours  = "min_sleep_opportunity_hours"
        case avoidHighIntensityNearBed = "avoid_high_intensity_near_bed"
        case caffeineCutoffTime        = "caffeine_cutoff_time"
        case preferredCategories       = "preferred_categories"
        case categoryWeights           = "category_weights"
        case stageACategories          = "stage_a_categories"
        case stageBCategories          = "stage_b_categories"
    }
}

struct PipelineResult: Codable {
    let message: String
    let userId: String
    let timestamp: String

    enum CodingKeys: String, CodingKey {
        case message
        case userId    = "user_id"
        case timestamp
    }
}

// MARK: - API Errors

enum APIError: LocalizedError {
    case noUserId
    case invalidURL
    case serverError(Int, String)
    case decodingError(String)

    var errorDescription: String? {
        switch self {
        case .noUserId:
            return "No user ID found. Please upload your health data first."
        case .invalidURL:
            return "Invalid server URL."
        case .serverError(let code, let msg):
            return "Server error \(code): \(msg)"
        case .decodingError(let msg):
            return "Could not parse response: \(msg)"
        }
    }
}

// MARK: - SleepAPIManager

@MainActor
class SleepAPIManager: ObservableObject {

    // ── Change to your Mac's IP when testing on a real device ─────────────────
    // Simulator  → http://127.0.0.1:8000
    // Real device → http://192.168.X.X:8000  (find with: ifconfig | grep "inet ")
    static let BASE_URL = "http://127.0.0.1:8000"
    // ──────────────────────────────────────────────────────────────────────────

    // Persisted across app launches via UserDefaults
    @Published var userId: String? {
        didSet { UserDefaults.standard.set(userId, forKey: "sleep_user_id") }
    }

    @Published var isLoading = false
    @Published var errorMessage: String?

    init() {
        // Restore saved user_id on launch
        self.userId = UserDefaults.standard.string(forKey: "sleep_user_id")
    }

    var hasUser: Bool { userId != nil }

    // ── Generic helpers ────────────────────────────────────────────────────────

    private func request<T: Decodable>(
        path: String,
        method: String = "GET",
        body: Data? = nil
    ) async throws -> T {
        guard let url = URL(string: Self.BASE_URL + path) else { throw APIError.invalidURL }

        var req = URLRequest(url: url)
        req.httpMethod = method
        if let body {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = body
        }

        let (data, response) = try await URLSession.shared.data(for: req)

        if let http = response as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
            let msg = String(data: data, encoding: .utf8) ?? "Unknown error"
            throw APIError.serverError(http.statusCode, msg)
        }

        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            throw APIError.decodingError(error.localizedDescription)
        }
    }

    private func userPath(_ suffix: String) throws -> String {
        guard let uid = userId else { throw APIError.noUserId }
        return "/users/\(uid)\(suffix)"
    }

    // ── Public API ─────────────────────────────────────────────────────────────

    /// Upload Apple Health export.xml.
    /// On success, user_id is automatically saved — no further setup needed.
    func uploadHealthData(fileURL: URL) async throws {
        guard let url = URL(string: Self.BASE_URL + "/upload/health-data") else {
            throw APIError.invalidURL
        }

        let fileData = try Data(contentsOf: fileURL)
        let boundary = UUID().uuidString

        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"export.xml\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: text/xml\r\n\r\n".data(using: .utf8)!)
        body.append(fileData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        req.httpBody = body

        let (data, response) = try await URLSession.shared.data(for: req)
        if let http = response as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
            let msg = String(data: data, encoding: .utf8) ?? "Unknown"
            throw APIError.serverError(http.statusCode, msg)
        }

        let result = try JSONDecoder().decode(UploadResponse.self, from: data)
        self.userId = result.userId   // ← saved to UserDefaults automatically
    }

    /// Save sleep preferences (wake time, goals, etc.)
    func savePreferences(_ prefs: SleepPreferencesRequest) async throws {
        let path = try userPath("/preferences")
        let body = try JSONEncoder().encode(prefs)
        let _: [String: String] = try await request(path: path, method: "POST", body: body)
    }

    /// Run the full analysis pipeline
    func runPipeline() async throws -> PipelineResult {
        let path = try userPath("/run/pipeline")
        return try await request(path: path, method: "POST")
    }

    /// Get tonight's sleep plan
    func getSleepPlan() async throws -> SleepPlan {
        let path = try userPath("/sleep/plan")
        return try await request(path: path)
    }

    /// Get wind-down content recommendations
    func getContentRecommendations(limit: Int = 10) async throws -> ContentResponse {
        let path = try userPath("/content/recommendations?limit=\(limit)")
        return try await request(path: path)
    }


    /// Run pipeline + return full bundle (plan + Stage A + Stage B content).
    /// Use this for the home screen on first load. For refreshes, use getBundle() instead.
    func runAndGetBundle() async throws -> TonightBundle {
        let path = try userPath("/tonight/bundle")
        return try await request(path: path, method: "POST")
    }

    /// Get the last generated bundle without re-running the pipeline.
    func getBundle() async throws -> TonightBundle {
        let path = try userPath("/tonight/bundle")
        return try await request(path: path)
    }

    /// Convenience: run pipeline then refresh all data
    func fullRefresh() async {
        isLoading = true
        errorMessage = nil
        do {
            _ = try await runPipeline()
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    /// Sign out / forget this user (does NOT delete server data)
    func clearUser() {
        userId = nil
        UserDefaults.standard.removeObject(forKey: "sleep_user_id")
    }
}


// MARK: - Example SwiftUI usage
/*
import SwiftUI
import UniformTypeIdentifiers

struct SleepRootView: View {
    @StateObject private var api = SleepAPIManager()

    var body: some View {
        if api.hasUser {
            SleepDashboardView(api: api)
        } else {
            OnboardingView(api: api)
        }
    }
}

// First-launch: ask user to upload their export.xml
struct OnboardingView: View {
    @ObservedObject var api: SleepAPIManager
    @State private var showPicker = false
    @State private var uploading = false
    @State private var error: String?

    var body: some View {
        VStack(spacing: 24) {
            Text("Welcome to Sleep Coach").font(.largeTitle)
            Text("Upload your Apple Health export to get started.")
                .multilineTextAlignment(.center)

            if uploading {
                ProgressView("Uploading…")
            } else {
                Button("Upload health data") { showPicker = true }
                    .buttonStyle(.borderedProminent)
            }

            if let error { Text(error).foregroundStyle(.red).font(.caption) }
        }
        .padding()
        .fileImporter(isPresented: $showPicker, allowedContentTypes: [.xml]) { result in
            guard let url = try? result.get() else { return }
            uploading = true
            Task {
                do {
                    try await api.uploadHealthData(fileURL: url)
                } catch {
                    self.error = error.localizedDescription
                }
                uploading = false
            }
        }
    }
}

struct SleepDashboardView: View {
    @ObservedObject var api: SleepAPIManager
    @State private var plan: SleepPlan?
    @State private var recs: [ContentRecommendation] = []

    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                if api.isLoading {
                    ProgressView("Refreshing…")
                } else {
                    if let plan {
                        VStack(spacing: 8) {
                            Text("Bedtime: \(plan.bedtimeStr)").font(.title2.bold())
                            Text("Wake up: \(plan.wakeStr)").font(.title2)
                            Text("Sleep opportunity: \(plan.sleepOpportunityMin) min")
                                .foregroundStyle(.secondary)
                        }
                        .padding()
                        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
                    }

                    List(recs) { rec in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(rec.title).bold()
                            Text(rec.explain).font(.caption).foregroundStyle(.secondary)
                            if let url = URL(string: rec.url) {
                                Link("Watch →", destination: url).font(.caption)
                            }
                        }
                    }
                }

                if let err = api.errorMessage {
                    Text(err).foregroundStyle(.red).font(.caption)
                }
            }
            .navigationTitle("Sleep Coach")
            .toolbar {
                Button("Refresh") { Task { await loadData() } }
            }
        }
        .task { await loadData() }
    }

    func loadData() async {
        await api.fullRefresh()
        plan = try? await api.getSleepPlan()
        let res = try? await api.getContentRecommendations()
        recs = res?.recommendations ?? []
    }
}
*/


// MARK: - Tonight Bundle

struct TonightBundle: Codable {
    let plan: SleepPlan
    let stages: Stages
    let userId: String?

    struct Stages: Codable {
        let stageA: StageContent
        let stageB: StageContent

        enum CodingKeys: String, CodingKey {
            case stageA = "stage_a"
            case stageB = "stage_b"
        }
    }

    struct StageContent: Codable {
        let label: String
        let recommendations: [ContentRecommendation]
    }

    enum CodingKeys: String, CodingKey {
        case plan, stages
        case userId = "user_id"
    }
}
import Foundation

// MARK: - Response Models

struct UploadResponse: Codable {
    let userId: String
    let message: String
    let nextStep: String
    enum CodingKeys: String, CodingKey {
        case userId = "user_id"; case message; case nextStep = "next_step"
    }
}

struct SleepPlan: Codable {
    let generatedAt: String
    let bedtimeMin: Double
    let wakeMin: Double
    let bedtimeStr: String
    let wakeStr: String
    let sleepOpportunityMin: Double
    let desiredSleepMin: Double
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
        case napCreditMin        = "nap_credit_min"
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
        case durationMin
    }
}

struct TonightBundle: Codable {
    let generatedAt: String
    let plan: SleepPlan
    let stages: Stages
    let userId: String?
    struct Stages: Codable {
        let stageA: StageContent
        let stageB: StageContent
        enum CodingKeys: String, CodingKey {
            case stageA = "stage_a"; case stageB = "stage_b"
        }
    }
    struct StageContent: Codable {
        let label: String
        let recommendations: [ContentRecommendation]
    }
    enum CodingKeys: String, CodingKey {
        case generatedAt = "generated_at"
        case plan, stages
        case userId = "user_id"
    }
}

struct SleepPreferencesRequest: Codable {
    var targetSleepHours: Double = 8.0
    var mustWakeBy: String?
    var preferredWakeTime: String?
    var noBedAfter: String?
    var minSleepOpportunityHours: Double?
    var avoidHighIntensityNearBed: Bool = false
    var caffeineCutoffTime: String?
    var preferredCategories: [String]?
    var categoryWeights: [String: Double]?
    var stageACategories: [String]?
    var stageBCategories: [String]?
    enum CodingKeys: String, CodingKey {
        case targetSleepHours = "target_sleep_hours"
        case mustWakeBy = "must_wake_by"
        case preferredWakeTime = "preferred_wake_time"
        case noBedAfter = "no_bed_after"
        case minSleepOpportunityHours = "min_sleep_opportunity_hours"
        case avoidHighIntensityNearBed = "avoid_high_intensity_near_bed"
        case caffeineCutoffTime = "caffeine_cutoff_time"
        case preferredCategories = "preferred_categories"
        case categoryWeights = "category_weights"
        case stageACategories = "stage_a_categories"
        case stageBCategories = "stage_b_categories"
    }
}

// MARK: - Nap Models

struct NapLog: Codable {
    let durationMinutes: Int
    let napTime: String?
    enum CodingKeys: String, CodingKey {
        case durationMinutes = "duration_minutes"
        case napTime = "nap_time"
    }
}

struct NapResponse: Codable {
    let message: String
    let nap: NapResponseEntry?
    
    struct NapResponseEntry: Codable {
        let durationMinutes: Double
        let napTime: String?
        enum CodingKeys: String, CodingKey {
            case durationMinutes = "duration_minutes"
            case napTime = "nap_time"
        }
    }
}

struct NapStatus: Codable {
    let nap: NapEntry?
    
    var hasNap: Bool { nap != nil }
    var durationMinutes: Int? { nap.map { Int($0.durationMinutes) } }
    var napTime: String? { nap?.napTime }
    
    struct NapEntry: Codable {
        let durationMinutes: Double
        let napTime: String?
        let date: String?
        enum CodingKeys: String, CodingKey {
            case durationMinutes = "duration_minutes"
            case napTime = "nap_time"
            case date
        }
    }
}
// MARK: - API Errors

enum APIError: LocalizedError {
    case noUserId, invalidURL, serverError(Int, String), decodingError(String)
    var errorDescription: String? {
        switch self {
        case .noUserId: return "No user ID. Please upload your health data first."
        case .invalidURL: return "Invalid server URL."
        case .serverError(let c, let m): return "Server error \(c): \(m)"
        case .decodingError(let m): return "Could not parse response: \(m)"
        }
    }
}

// MARK: - SleepAPIManager

@MainActor
@Observable
class SleepAPIManager {

    // Change to your Mac's local IP when running on a real device
    static let BASE_URL = "http://10.10.231.93:8000"

    var userId: String? {
        didSet { UserDefaults.standard.set(userId, forKey: "sleep_user_id") }
    }
    var isLoading = false
    var errorMessage: String?

    init() {
        self.userId = UserDefaults.standard.string(forKey: "sleep_user_id")
    }

    var hasUser: Bool { userId != nil }

    private func request<T: Decodable>(path: String, method: String = "GET", body: Data? = nil) async throws -> T {
        guard let url = URL(string: Self.BASE_URL + path) else { throw APIError.invalidURL }
        var req = URLRequest(url: url)
        req.httpMethod = method
        if let body { req.setValue("application/json", forHTTPHeaderField: "Content-Type"); req.httpBody = body }
        let (data, response) = try await URLSession.shared.data(for: req)
        if let http = response as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
            throw APIError.serverError(http.statusCode, String(data: data, encoding: .utf8) ?? "Unknown")
        }
        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch DecodingError.keyNotFound(let key, let context) {
            throw APIError.decodingError("Missing key: \(key.stringValue) at \(context.codingPath)")
        } catch DecodingError.typeMismatch(let type, let context) {
            throw APIError.decodingError("Type mismatch: expected \(type) at \(context.codingPath.map(\.stringValue))")
        } catch DecodingError.valueNotFound(let type, let context) {
            throw APIError.decodingError("Value not found: \(type) at \(context.codingPath.map(\.stringValue))")
        } catch {
            throw APIError.decodingError(error.localizedDescription)
        }
    }

    private func userPath(_ suffix: String) throws -> String {
        guard let uid = userId else { throw APIError.noUserId }
        return "/users/\(uid)\(suffix)"
    }

    func uploadHealthData(fileURL: URL) async throws {
        guard let url = URL(string: Self.BASE_URL + "/upload/health-data") else { throw APIError.invalidURL }
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
            throw APIError.serverError(http.statusCode, String(data: data, encoding: .utf8) ?? "Unknown")
        }
        let result = try JSONDecoder().decode(UploadResponse.self, from: data)
        self.userId = result.userId
    }

    func savePreferences(_ prefs: SleepPreferencesRequest) async throws {
        let path = try userPath("/preferences")
        let body = try JSONEncoder().encode(prefs)
        let (data, response) = try await URLSession.shared.data(for: {
            var req = URLRequest(url: URL(string: Self.BASE_URL + path)!)
            req.httpMethod = "POST"
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = body
            return req
        }())
        if let http = response as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
            throw APIError.serverError(http.statusCode, String(data: data, encoding: .utf8) ?? "Unknown")
        }
    }

    func runAndGetBundle() async throws -> TonightBundle {
        return try await request(path: try userPath("/tonight/bundle"), method: "POST")
    }

    func getBundle() async throws -> TonightBundle {
        return try await request(path: try userPath("/tonight/bundle"))
    }

    // MARK: - Nap API

    func logNap(durationMinutes: Int, napTime: String? = nil) async throws -> NapResponse {
        let path = try userPath("/nap")
        let nap = NapLog(durationMinutes: durationMinutes, napTime: napTime)
        let body = try JSONEncoder().encode(nap)
        return try await request(path: path, method: "POST", body: body)
    }

    func getTodayNap() async throws -> NapStatus {
        let path = try userPath("/nap")
        return try await request(path: path)
    }

    func clearUser() {
        userId = nil
        UserDefaults.standard.removeObject(forKey: "sleep_user_id")
    }
}

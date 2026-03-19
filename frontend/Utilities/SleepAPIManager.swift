import Foundation
import FirebaseAuth
import FirebaseFirestore
import Combine
import ZIPFoundation

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
        case durationMin = "duration_min"
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
class SleepAPIManager: ObservableObject {

    static let BASE_URL = "http://127.0.0.1:8000"

    var firebaseAuth: FirebaseAuthManager
    @Published var userId: String?
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var hasUserData: Bool = false

    init(firebaseAuth: FirebaseAuthManager) {
        self.firebaseAuth = firebaseAuth
        self.userId = UserDefaults.standard.string(forKey: "sleep_user_id")
    }

    private func persistUserId() {
        UserDefaults.standard.set(userId, forKey: "sleep_user_id")
    }

    var hasUser: Bool { userId != nil }

    var isEmailVerified: Bool {
        guard let user = firebaseAuth.user else { return false }
        return user.isEmailVerified
    }

    func sendEmailVerification(completion: ((Error?) -> Void)? = nil) {
        firebaseAuth.user?.sendEmailVerification(completion: completion)
    }

    private func request<T: Decodable>(path: String, method: String = "GET", body: Data? = nil) async throws -> T {
        guard let url = URL(string: Self.BASE_URL + path) else { throw APIError.invalidURL }
        var req = URLRequest(url: url)
        req.httpMethod = method
        
        if let token = firebaseAuth.idToken {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        if let body { 
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = body 
        }
        
        let (data, response) = try await URLSession.shared.data(for: req)
        
        if let http = response as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
            if http.statusCode == 401 {
                await firebaseAuth.refreshToken()
                return try await request(path: path, method: method, body: body)
            }
            throw APIError.serverError(http.statusCode, String(data: data, encoding: .utf8) ?? "Unknown")
        }
        
        return try JSONDecoder().decode(T.self, from: data)
    }

    private func userPath(_ suffix: String) throws -> String {
        guard let uid = userId else { throw APIError.noUserId }
        return "/users/\(uid)\(suffix)"
    }

    func uploadHealthData(fileURL: URL) async throws {
        guard let uid = firebaseAuth.user?.uid else { throw APIError.noUserId }
        guard let url = URL(string: Self.BASE_URL + "/upload/health-data") else { throw APIError.invalidURL }
        
        let fileManager = FileManager.default
        let tempDir = fileManager.temporaryDirectory
        
        let zipURL = tempDir.appendingPathComponent("export.zip")
        if fileManager.fileExists(atPath: zipURL.path) { try? fileManager.removeItem(at: zipURL) }
        
        guard let archive = Archive(url: zipURL, accessMode: .create) else {
            throw APIError.decodingError("Could not create ZIP archive")
        }
        try archive.addEntry(with: "export.xml", fileURL: fileURL)
        
        let boundary = "Boundary-\(UUID().uuidString)"
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        req.timeoutInterval = 600 
        
        if let token = firebaseAuth.idToken {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let combinedUploadURL = tempDir.appendingPathComponent("final_upload.tmp")
        if fileManager.fileExists(atPath: combinedUploadURL.path) { 
            try? fileManager.removeItem(at: combinedUploadURL) 
        }
        
        fileManager.createFile(atPath: combinedUploadURL.path, contents: nil)
        let handle = try FileHandle(forWritingTo: combinedUploadURL)
        
        let header = "--\(boundary)\r\nContent-Disposition: form-data; name=\"file\"; filename=\"export.zip\"\r\nContent-Type: application/zip\r\n\r\n"
        try handle.write(contentsOf: header.data(using: .utf8)!)
        
        let zipHandle = try FileHandle(forReadingFrom: zipURL)
        while let chunk = try zipHandle.read(upToCount: 1024 * 1024) {
            try handle.write(contentsOf: chunk)
        }
        try zipHandle.close()
        
        try handle.write(contentsOf: "\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        try handle.close()

        let config = URLSessionConfiguration.default
        config.timeoutIntervalForResource = 1200 
        let session = URLSession(configuration: config)

        let (data, response) = try await session.upload(for: req, fromFile: combinedUploadURL)

        try? fileManager.removeItem(at: zipURL)
        try? fileManager.removeItem(at: combinedUploadURL)

        if let http = response as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
            throw APIError.serverError(http.statusCode, String(data: data, encoding: .utf8) ?? "Unknown")
        }
        
        _ = try JSONDecoder().decode(UploadResponse.self, from: data)
        await MainActor.run {
            self.userId = uid
            persistUserId()
        }
    }

    func savePreferences(_ prefs: SleepPreferencesRequest) async throws {
        let path = try userPath("/preferences")
        let body = try JSONEncoder().encode(prefs)
        _ = try await request(path: path, method: "POST", body: body) as UploadResponse
    }

    func runAndGetBundle() async throws -> TonightBundle {
        return try await request(path: try userPath("/tonight/bundle"), method: "POST")
    }

    func getBundle() async throws -> TonightBundle {
        return try await request(path: try userPath("/tonight/bundle"))
    }
    func getBundleWithRetry(retries: Int = 5) async throws -> TonightBundle {
        for i in 0..<retries {
            do {
                print("🔄 Attempting to fetch bundle (Try \(i + 1))...")
                return try await getBundle()
            } catch {
                // If the data isn't processed yet, the server usually returns 404
                if i < retries - 1 {
                    print("⏳ Data not ready yet, waiting 3 seconds...")
                    try? await Task.sleep(nanoseconds: 3 * 1_000_000_000)
                } else {
                    throw error
                }
            }
        }
        throw APIError.serverError(404, "Data processing timed out.")
    }

    func clearUser() {
        userId = nil
        UserDefaults.standard.removeObject(forKey: "sleep_user_id")
        firebaseAuth.signOut()
    }

    func checkUserDataExists() async {
        guard let uid = firebaseAuth.user?.uid else {
            await MainActor.run { hasUserData = false }
            return
        }
        
        let db = Firestore.firestore()
        // Updated to check the collection count instead of a single document
        let colRef = db.collection("users").document(uid).collection("sleep_records")
        
        do {
            let snapshot = try await colRef.limit(to: 1).getDocuments()
            await MainActor.run {
                self.hasUserData = !snapshot.isEmpty
            }
        } catch {
            await MainActor.run { self.hasUserData = false }
        }
    }

    func getProcessingStatus() async throws -> String {
        guard let uid = firebaseAuth.user?.uid else { throw APIError.noUserId }
        let path = "/users/\(uid)/status"
        
        // We use a simple dictionary fetch here since request<T> expects a Decodable
        guard let url = URL(string: Self.BASE_URL + path) else { throw APIError.invalidURL }
        var req = URLRequest(url: url)
        if let token = firebaseAuth.idToken {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        let (data, _) = try await URLSession.shared.data(for: req)
        if let json = try? JSONSerialization.jsonObject(with: data) as? [String: String],
           let status = json["status"] {
            return status
        }
        return "unknown"
    }
}

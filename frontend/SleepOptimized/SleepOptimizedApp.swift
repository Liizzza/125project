import SwiftUI

@main
struct SleepOptimizedApp: App {
    @StateObject private var api = SleepAPIManager()

    var body: some Scene {
        WindowGroup {
            // If user_id already saved → go straight to Dashboard
            // Otherwise → go through onboarding (Welcome → Login → Upload → Preferences)
            if api.hasUser {
                NavigationStack {
                    DashboardView()
                        .environmentObject(api)
                }
            } else {
                WelcomeView()
                    .environmentObject(api)
            }
        }
    }
}
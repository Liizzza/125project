import SwiftUI

@main
struct SleepOptimizedApp: App {
    @State private var api = SleepAPIManager()

    var body: some Scene {
        WindowGroup {
            NavigationStack {
                if api.hasUser {
                    DashboardView()
                } else {
                    WelcomeView()
                }
            }
            .environment(api)
        }
    }
}

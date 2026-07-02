import SwiftUI
import IcarusKit

/// The shell's left rail: brand mark, the five nav rows, and a footer showing the
/// REAL connected repo (from /status) — never a fabricated tenant name.
struct SidebarView: View {
    @Binding var selected: ShellSurface
    let status: StatusModel

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 7) {
                dot(0xE6675A); dot(0xE6B24A); dot(0x57B85B)
            }
            .padding(.leading, 4).padding(.top, 2)

            HStack(alignment: .bottom, spacing: 9) {
                MarkView(height: 26)
                Text("Icarus").font(.system(size: 19, weight: .semibold)).foregroundStyle(Theme.ink)
            }
            .padding(.leading, 4).padding(.top, 22).padding(.bottom, 24)

            VStack(spacing: 3) {
                ForEach(ShellSurface.allCases) { s in
                    NavRow(surface: s, selected: $selected)
                }
            }

            Spacer(minLength: 24)

            VStack(alignment: .leading, spacing: 3) {
                MonoLabel("COMPANY BRAIN")
                Text(status.repo ?? "—")
                    .font(Theme.mono(13)).foregroundStyle(Theme.ink)
                    .padding(.top, 3)
                Text("Zero training on code")
                    .font(.system(size: 12)).foregroundStyle(Theme.muted)
            }
            .padding(.leading, 4)
        }
        .padding(16)
        .frame(width: 210)
        .frame(maxHeight: .infinity, alignment: .top)
        .background(Color(hex: 0xF2F0E9))
    }

    private func dot(_ hex: UInt32) -> some View {
        Circle().fill(Color(hex: hex)).frame(width: 11, height: 11)
    }
}

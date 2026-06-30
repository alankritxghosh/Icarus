import SwiftUI

/// The overlay's content. Brick A2 is a placeholder text field only — no
/// networking, no answer rendering, no voice (those arrive in later bricks).
struct OverlayView: View {
    @State private var question = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            TextField("Ask Icarus about the codebase…", text: $question)
                .textFieldStyle(.plain)
                .font(.title3)
        }
        .padding(20)
        .frame(width: 560)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16))
    }
}

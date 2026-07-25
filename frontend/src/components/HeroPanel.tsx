export function HeroPanel() {
    return (
        <div className="flex flex-col justify-center h-full py-16 lg:py-0">
            <h1 className="text-5xl xl:text-6xl font-bold leading-tight text-white mb-4">
                ArduPilot
            </h1>
            <div className="mb-8">
                <span className="text-4xl xl:text-5xl font-bold text-logo-gradient">
                    CustomBuild
                </span>
            </div>

            <p className="text-gray-500 text-lg leading-relaxed max-w-sm mb-8">
                Build exactly the firmware you need. Choose your vehicle, board, and feature set,
                and we'll compile it for you.
            </p>

            <p className="text-logo-gradient text-xl xl:text-2xl font-mono uppercase tracking-wider">
                Versatile · Trusted · Open
            </p>
        </div>
    );
}

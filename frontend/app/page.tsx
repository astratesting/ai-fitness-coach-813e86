import Link from "next/link";
import { SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/nextjs";
import {
  Activity,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  Dumbbell,
  Flame,
  LineChart,
  Salad,
  ShieldCheck,
  Sparkles,
  Timer,
  TrendingUp,
  Users,
  Utensils,
} from "lucide-react";

const stats = [
  { label: "Plans generated", value: "12k+" },
  { label: "Avg. weekly adherence", value: "82%" },
  { label: "Minutes to first plan", value: "4" },
];

const features = [
  {
    icon: Dumbbell,
    title: "Adaptive workout plans",
    description:
      "Get strength, cardio, mobility, and recovery sessions tuned to your goals, available equipment, schedule, and current fitness level.",
  },
  {
    icon: Salad,
    title: "Nutrition built around real life",
    description:
      "Receive calorie, macro, hydration, and meal guidance that adjusts to preferences, progress, and busy workdays.",
  },
  {
    icon: LineChart,
    title: "Progress tracking that learns",
    description:
      "Track biometrics, consistency, energy, and performance trends so recommendations improve as your body changes.",
  },
];

const onboardingSteps = [
  "Share biometrics, goals, dietary preferences, and activity level.",
  "AI creates personalized workout and nutrition plans for your week.",
  "Log progress, get adjustments, and keep improving with clear guidance.",
];

const planHighlights = [
  "45-minute strength sessions for lunch breaks",
  "High-protein meals with grocery-friendly ingredients",
  "Recovery and mobility blocks when stress or fatigue rises",
  "Weekly progress review with practical next actions",
];

const dashboardMetrics = [
  { label: "Workout streak", value: "9 days", icon: Flame },
  { label: "Plan completion", value: "87%", icon: CheckCircle2 },
  { label: "Weekly active time", value: "214 min", icon: Timer },
  { label: "Goal trend", value: "+18%", icon: TrendingUp },
];

export default function HomePage() {
  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute left-1/2 top-0 h-[34rem] w-[34rem] -translate-x-1/2 rounded-full bg-cyan-500/20 blur-3xl" />
        <div className="absolute right-0 top-80 h-96 w-96 rounded-full bg-emerald-500/10 blur-3xl" />
      </div>

      <header className="mx-auto flex w-full max-w-7xl items-center justify-between px-6 py-6 lg:px-8">
        <Link href="/" className="flex items-center gap-3" aria-label="FitPilot home">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-cyan-400 text-slate-950 shadow-lg shadow-cyan-400/20">
            <Activity className="h-6 w-6" aria-hidden="true" />
          </div>
          <div>
            <p className="text-lg font-bold tracking-tight">FitPilot AI</p>
            <p className="text-xs text-slate-400">Personal fitness coach</p>
          </div>
        </Link>

        <nav className="hidden items-center gap-8 text-sm font-medium text-slate-300 md:flex" aria-label="Primary navigation">
          <a href="#features" className="transition hover:text-white">
            Features
          </a>
          <a href="#plans" className="transition hover:text-white">
            Plans
          </a>
          <a href="#progress" className="transition hover:text-white">
            Progress
          </a>
        </nav>

        <div className="flex items-center gap-3">
          <SignedOut>
            <SignInButton mode="modal">
              <button className="rounded-full border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-cyan-300/70 hover:text-white">
                Sign in
              </button>
            </SignInButton>
            <Link
              href="/onboarding"
              className="hidden rounded-full bg-cyan-400 px-4 py-2 text-sm font-bold text-slate-950 shadow-lg shadow-cyan-400/20 transition hover:bg-cyan-300 sm:inline-flex"
            >
              Start free
            </Link>
          </SignedOut>
          <SignedIn>
            <Link
              href="/dashboard"
              className="rounded-full bg-cyan-400 px-4 py-2 text-sm font-bold text-slate-950 shadow-lg shadow-cyan-400/20 transition hover:bg-cyan-300"
            >
              Dashboard
            </Link>
            <UserButton afterSignOutUrl="/" />
          </SignedIn>
        </div>
      </header>

      <section className="mx-auto grid w-full max-w-7xl items-center gap-12 px-6 pb-20 pt-10 lg:grid-cols-[1.05fr_0.95fr] lg:px-8 lg:pb-28 lg:pt-16">
        <div>
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-4 py-2 text-sm font-semibold text-cyan-200">
            <Sparkles className="h-4 w-4" aria-hidden="true" />
            AI coaching for busy professionals
          </div>
          <h1 className="max-w-4xl text-5xl font-black tracking-tight text-white sm:text-6xl lg:text-7xl">
            Fitness and nutrition plans that adapt to your body.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
            FitPilot AI turns biometrics, goals, schedule, and progress into clear weekly workout and nutrition guidance built for demanding calendars.
          </p>
          <div className="mt-10 flex flex-col gap-4 sm:flex-row">
            <Link
              href="/onboarding"
              className="inline-flex items-center justify-center gap-2 rounded-full bg-cyan-400 px-7 py-4 text-base font-bold text-slate-950 shadow-xl shadow-cyan-400/20 transition hover:bg-cyan-300"
            >
              Build my plan
              <ArrowRight className="h-5 w-5" aria-hidden="true" />
            </Link>
            <Link
              href="/dashboard"
              className="inline-flex items-center justify-center rounded-full border border-white/10 px-7 py-4 text-base font-bold text-white transition hover:border-white/30 hover:bg-white/5"
            >
              View dashboard
            </Link>
          </div>

          <div className="mt-12 grid max-w-2xl grid-cols-3 gap-4">
            {stats.map((stat) => (
              <div key={stat.label} className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
                <p className="text-2xl font-black text-white">{stat.value}</p>
                <p className="mt-1 text-sm text-slate-400">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="relative">
          <div className="rounded-[2rem] border border-white/10 bg-white/[0.06] p-4 shadow-2xl shadow-cyan-950/40 backdrop-blur">
            <div className="rounded-[1.5rem] bg-slate-900 p-5">
              <div className="flex items-center justify-between border-b border-white/10 pb-5">
                <div>
                  <p className="text-sm text-slate-400">Today&apos;s plan</p>
                  <h2 className="mt-1 text-2xl font-bold">Strength + nutrition</h2>
                </div>
                <div className="rounded-2xl bg-emerald-400/10 px-3 py-2 text-sm font-bold text-emerald-300">
                  On track
                </div>
              </div>

              <div className="mt-6 space-y-4">
                <div className="rounded-3xl bg-gradient-to-br from-cyan-400 to-emerald-300 p-5 text-slate-950">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-bold uppercase tracking-wide">Workout</p>
                    <Dumbbell className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <h3 className="mt-4 text-2xl font-black">Full-body strength</h3>
                  <p className="mt-2 text-sm font-semibold text-slate-800">
                    6 movements · 42 minutes · hotel gym friendly
                  </p>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
                    <Utensils className="h-6 w-6 text-cyan-300" aria-hidden="true" />
                    <p className="mt-4 text-sm text-slate-400">Daily target</p>
                    <p className="text-2xl font-black">2,180 kcal</p>
                    <p className="text-sm text-slate-400">165g protein</p>
                  </div>
                  <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
                    <BarChart3 className="h-6 w-6 text-emerald-300" aria-hidden="true" />
                    <p className="mt-4 text-sm text-slate-400">Readiness</p>
                    <p className="text-2xl font-black">84%</p>
                    <p className="text-sm text-slate-400">Intensity approved</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="features" className="border-y border-white/10 bg-white/[0.03] py-20">
        <div className="mx-auto w-full max-w-7xl px-6 lg:px-8">
          <div className="max-w-3xl">
            <p className="text-sm font-bold uppercase tracking-[0.3em] text-cyan-300">MVP features</p>
            <h2 className="mt-4 text-4xl font-black tracking-tight sm:text-5xl">
              One coach for workouts, meals, and accountability.
            </h2>
          </div>
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {features.map((feature) => {
              const Icon = feature.icon;
              return (
                <article key={feature.title} className="rounded-[2rem] border border-white/10 bg-slate-900/70 p-7 shadow-xl shadow-slate-950/20">
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-cyan-400/10 text-cyan-300">
                    <Icon className="h-6 w-6" aria-hidden="true" />
                  </div>
                  <h3 className="mt-6 text-xl font-bold">{feature.title}</h3>
                  <p className="mt-3 leading-7 text-slate-400">{feature.description}</p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section id="plans" className="mx-auto grid w-full max-w-7xl gap-10 px-6 py-20 lg:grid-cols-2 lg:px-8">
        <div>
          <p className="text-sm font-bold uppercase tracking-[0.3em] text-emerald-300">Personalization</p>
          <h2 className="mt-4 text-4xl font-black tracking-tight sm:text-5xl">
            Built from biometrics, not generic templates.
          </h2>
          <p className="mt-5 text-lg leading-8 text-slate-300">
            Onboarding captures age, height, weight, goals, activity level, constraints, and food preferences. FitPilot AI turns that data into realistic weekly guidance.
          </p>
          <ol className="mt-8 space-y-4">
            {onboardingSteps.map((step, index) => (
              <li key={step} className="flex gap-4 rounded-3xl border border-white/10 bg-white/[0.03] p-5">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-400 text-sm font-black text-slate-950">
                  {index + 1}
                </span>
                <span className="text-slate-300">{step}</span>
              </li>
            ))}
          </ol>
        </div>

        <div className="rounded-[2rem] border border-white/10 bg-slate-900/80 p-7">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-400/10 text-emerald-300">
              <ShieldCheck className="h-6 w-6" aria-hidden="true" />
            </div>
            <div>
              <p className="text-sm text-slate-400">Generated weekly plan</p>
              <h3 className="text-2xl font-bold">Professional cut phase</h3>
            </div>
          </div>
          <div className="mt-8 space-y-4">
            {planHighlights.map((item) => (
              <div key={item} className="flex items-start gap-3 rounded-2xl bg-white/[0.04] p-4">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-cyan-300" aria-hidden="true" />
                <p className="text-slate-300">{item}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="progress" className="mx-auto w-full max-w-7xl px-6 pb-24 lg:px-8">
        <div className="rounded-[2rem] border border-white/10 bg-gradient-to-br from-slate-900 to-slate-950 p-7 lg:p-10">
          <div className="grid gap-10 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
            <div>
              <p className="text-sm font-bold uppercase tracking-[0.3em] text-cyan-300">Progress dashboard</p>
              <h2 className="mt-4 text-4xl font-black tracking-tight sm:text-5xl">
                Measure effort, recovery, and outcomes in one view.
              </h2>
              <p className="mt-5 leading-8 text-slate-300">
                Keep users engaged with clear metrics, weekly summaries, adherence insights, and AI recommendations that respond to logged progress.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {dashboardMetrics.map((metric) => {
                const Icon = metric.icon;
                return (
                  <div key={metric.label} className="rounded-3xl border border-white/10 bg-white/[0.04] p-6">
                    <Icon className="h-7 w-7 text-emerald-300" aria-hidden="true" />
                    <p className="mt-6 text-sm text-slate-400">{metric.label}</p>
                    <p className="mt-1 text-3xl font-black">{metric.value}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto w-full max-w-7xl px-6 pb-24 lg:px-8">
        <div className="rounded-[2rem] bg-cyan-400 p-8 text-slate-950 md:p-12">
          <div className="grid gap-8 md:grid-cols-[1fr_auto] md:items-center">
            <div>
              <div className="flex items-center gap-2 text-sm font-black uppercase tracking-[0.25em]">
                <Users className="h-5 w-5" aria-hidden="true" />
                Built for professionals 25–45
              </div>
              <h2 className="mt-4 text-4xl font-black tracking-tight sm:text-5xl">
                Start with biometrics. Leave with plan.
              </h2>
              <p className="mt-4 max-w-2xl text-lg font-medium text-slate-800">
                Create account, complete onboarding, and generate personalized training and nutrition guidance in minutes.
              </p>
            </div>
            <Link
              href="/onboarding"
              className="inline-flex items-center justify-center gap-2 rounded-full bg-slate-950 px-7 py-4 text-base font-bold text-white transition hover:bg-slate-800"
            >
              Start onboarding
              <ArrowRight className="h-5 w-5" aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}

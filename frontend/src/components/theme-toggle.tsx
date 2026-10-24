import { Moon, Sun } from "lucide-react"
import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"

type Tema = "light" | "dark"

function temaInicial(): Tema {
  try {
    const salvo = localStorage.getItem("tema")
    if (salvo === "light" || salvo === "dark") return salvo
  } catch {
    // localStorage indisponível: segue a preferência do sistema
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

export function ThemeToggle() {
  const [tema, setTema] = useState<Tema>(temaInicial)

  useEffect(() => {
    document.documentElement.classList.toggle("dark", tema === "dark")
    try {
      localStorage.setItem("tema", tema)
    } catch {
      // ignora
    }
  }, [tema])

  return (
    <Button
      variant="outline"
      size="icon"
      aria-label={tema === "dark" ? "Usar tema claro" : "Usar tema escuro"}
      onClick={() => setTema(tema === "dark" ? "light" : "dark")}
    >
      {tema === "dark" ? <Sun /> : <Moon />}
    </Button>
  )
}

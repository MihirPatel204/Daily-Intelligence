import { NextResponse } from "next/server";
import { exec } from "child_process";
import { promisify } from "util";

export const dynamic = "force-dynamic";

const execAsync = promisify(exec);

export async function GET() {
  try {
    const command = `python "C:\\Users\\mihir patel\\.gemini\\antigravity-ide\\brain\\80a79557-0463-474b-a5df-04e169845498\\scratch\\check_active_queries.py"`;
    console.log("Executing command via Next.js server:", command);
    
    const { stdout, stderr } = await execAsync(command);
    
    return NextResponse.json({
      status: "success",
      stdout: stdout,
      stderr: stderr,
    });
  } catch (error: any) {
    return NextResponse.json({
      status: "error",
      message: error.message,
      stdout: error.stdout,
      stderr: error.stderr,
    }, { status: 500 });
  }
}

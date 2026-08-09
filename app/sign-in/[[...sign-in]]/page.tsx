import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return <div className="authPage"><SignIn/></div>;
}

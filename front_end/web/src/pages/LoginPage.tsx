import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Card, Form, Input, message, Typography } from "antd";
import { ReloadOutlined, UserOutlined, LockOutlined, SafetyOutlined } from "@ant-design/icons";
import { api, setToken, ApiBizError } from "../api/client";
import { useAuth } from "../context/AuthContext";
import logo from "../assets/logo.jpg";

interface CaptchaState {
  token: string;
  image: string; // data URL
}

export default function LoginPage() {
  const navigate = useNavigate();
  const { loggedIn, markLoggedIn } = useAuth();
  const [captcha, setCaptcha] = useState<CaptchaState | null>(null);
  const [captchaLoading, setCaptchaLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm();

  const refreshCaptcha = useCallback(async () => {
    setCaptchaLoading(true);
    try {
      const data = await api.getCaptcha();
      setToken(data.session_token);
      setCaptcha({
        token: data.session_token,
        image: `data:${data.content_type};base64,${data.image_base64}`,
      });
    } catch (error) {
      const msg = error instanceof ApiBizError ? error.message : "获取验证码失败";
      message.error(msg);
    } finally {
      setCaptchaLoading(false);
    }
  }, []);

  useEffect(() => {
    if (loggedIn) {
      navigate("/", { replace: true });
      return;
    }
    refreshCaptcha();
  }, [loggedIn, navigate, refreshCaptcha]);

  const handleLogin = async (values: {
    username: string;
    password: string;
    captcha: string;
  }) => {
    if (!captcha) {
      message.warning("请先获取验证码");
      return;
    }
    setSubmitting(true);
    try {
      const data = await api.login({
        session_token: captcha.token,
        username: values.username,
        password: values.password,
        captcha: values.captcha,
      });
      setToken(data.session_token);
      markLoggedIn(data.username);
      message.success(`欢迎回来，${data.username}`);
      navigate("/", { replace: true });
    } catch (error) {
      const msg = error instanceof ApiBizError ? error.message : "登录失败";
      message.error(msg);
      refreshCaptcha();
      form.setFieldValue("captcha", "");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(135deg, #e0ecff 0%, #f5f7fa 100%)",
      }}
    >
      <Card style={{ width: 400, boxShadow: "0 4px 24px rgba(0,0,0,0.08)" }}>
        <div style={{ textAlign: "center" }}>
          <img
            src={logo}
            alt="学院教学小助手 Logo"
            style={{ width: 64, height: 64, objectFit: "contain", borderRadius: 16 }}
          />
          <Typography.Title level={3} style={{ marginTop: 12, marginBottom: 4 }}>
            学院教学小助手
          </Typography.Title>
        </div>
        <Typography.Paragraph type="secondary" style={{ textAlign: "center" }}>
          请使用教务系统账号登录
        </Typography.Paragraph>
        <Form form={form} layout="vertical" onFinish={handleLogin}>
          <Form.Item
            name="username"
            rules={[{ required: true, message: "请输入学号" }]}
          >
            <Input size="large" prefix={<UserOutlined />} placeholder="学号" />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, message: "请输入密码" }]}
          >
            <Input.Password
              size="large"
              prefix={<LockOutlined />}
              placeholder="教务系统密码"
            />
          </Form.Item>
          <Form.Item>
            <div style={{ display: "flex", gap: 12 }}>
              <Form.Item
                name="captcha"
                noStyle
                rules={[{ required: true, message: "请输入验证码" }]}
              >
                <Input
                  size="large"
                  prefix={<SafetyOutlined />}
                  placeholder="验证码"
                  style={{ flex: 1 }}
                />
              </Form.Item>
              {captcha ? (
                <img
                  src={captcha.image}
                  alt="验证码"
                  onClick={refreshCaptcha}
                  style={{
                    height: 40,
                    cursor: "pointer",
                    border: "1px solid #d9d9d9",
                    borderRadius: 6,
                  }}
                  title="点击刷新验证码"
                />
              ) : (
                <Button onClick={refreshCaptcha} loading={captchaLoading}>
                  获取验证码
                </Button>
              )}
              <Button
                icon={<ReloadOutlined />}
                onClick={refreshCaptcha}
                loading={captchaLoading}
              />
            </div>
          </Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            size="large"
            block
            loading={submitting}
          >
            登录
          </Button>
        </Form>
        <Typography.Paragraph type="secondary" style={{ marginTop: 16, fontSize: 12 }}>
          密码与验证码仅用于本次登录请求，不会被保存到浏览器本地。
        </Typography.Paragraph>
      </Card>
    </div>
  );
}

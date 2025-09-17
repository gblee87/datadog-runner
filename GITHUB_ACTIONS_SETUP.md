# GitHub Actions CI/CD 설정 가이드

이 문서는 Datadog Runner 프로젝트의 GitHub Actions CI/CD 파이프라인을 설정하는 완전한 가이드입니다.

## 🎯 개요

GitHub Actions를 통해 다음과 같은 자동화된 CI/CD 파이프라인이 구축됩니다:

- **자동 빌드**: 모든 서비스의 Docker 이미지 빌드 및 ECR 푸시
- **자동 배포**: main 브랜치 푸시 시 EKS에 자동 배포
- **수동 배포**: workflow_dispatch를 통한 버전 지정 배포
- **단일 환경**: 단순한 구조로 default 네임스페이스에 배포

## 📋 사전 준비사항

### 1. EKS 클러스터 생성

```bash
# EKS 클러스터 생성
./scripts/create-eks-cluster.sh datadog-runner
```

### 2. AWS IAM 사용자 생성

GitHub Actions용 IAM 사용자를 생성하고 다음 정책을 연결하세요:

#### 정책 1: ECR 접근 권한
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ecr:GetAuthorizationToken",
                "ecr:BatchCheckLayerAvailability",
                "ecr:GetDownloadUrlForLayer",
                "ecr:BatchGetImage",
                "ecr:BatchImportLayerPart",
                "ecr:InitiateLayerUpload",
                "ecr:UploadLayerPart",
                "ecr:CompleteLayerUpload",
                "ecr:PutImage",
                "ecr:CreateRepository",
                "ecr:DescribeRepositories",
                "ecr:ListRepositories"
            ],
            "Resource": "*"
        }
    ]
}
```

#### 정책 2: EKS 접근 권한
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "eks:DescribeCluster",
                "eks:ListClusters",
                "sts:GetCallerIdentity"
            ],
            "Resource": "*"
        }
    ]
}
```

### 3. EKS 클러스터에 IAM 사용자 권한 추가

EKS 클러스터에서 GitHub Actions IAM 사용자가 kubectl을 사용할 수 있도록 권한을 추가하세요:

```bash
# 클러스터 설정
aws eks update-kubeconfig --region us-east-1 --name datadog-runner

kubectl edit configmap aws-auth -n kube-system
```

ConfigMap에 다음 내용을 추가:
```yaml
mapUsers: |
  - userarn: arn:aws:iam::YOUR_ACCOUNT_ID:user/github-actions-user
    username: github-actions-user
    groups:
      - system:masters
```

## 🔐 GitHub Secrets 설정

Repository Settings → Secrets and variables → Actions에서 다음 secrets를 설정하세요:

### 필수 Secrets

| Secret Name | Description | 예시 |
|-------------|-------------|------|
| `AWS_ACCESS_KEY_ID` | GitHub Actions IAM 사용자의 Access Key ID | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | GitHub Actions IAM 사용자의 Secret Access Key | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |

**참고**: EKS 클러스터 이름은 워크플로우에서 `datadog-runner`로 하드코딩되어 있습니다.

### 선택적 Secrets (Datadog 모니터링용)

| Secret Name | Description |
|-------------|-------------|
| `DATADOG_API_KEY` | Datadog API 키 |
| `DATADOG_APP_KEY` | Datadog Application 키 |

## 🚀 워크플로우 사용법

### 1. 자동 배포

main 브랜치에 푸시하면 자동으로 배포됩니다:

```bash
git add .
git commit -m "feat: new feature"
git push origin main
```

### 2. 수동 배포

1. GitHub Repository → Actions 탭 이동
2. "Build and Deploy to EKS" 워크플로우 선택
3. "Run workflow" 버튼 클릭
4. 원하는 버전 태그 입력 (선택사항)
5. "Run workflow" 실행

## 📊 모니터링 및 알림

### 1. 워크플로우 상태 확인
- Actions 탭에서 모든 워크플로우 실행 상태를 확인할 수 있습니다.
- 실패한 워크플로우는 빨간색으로 표시됩니다.

### 2. 배포 상태 확인

배포 후 다음 명령어로 상태를 확인할 수 있습니다:

```bash
# EKS 클러스터 연결
aws eks update-kubeconfig --region us-east-1 --name datadog-runner

# 배포 상태 확인
kubectl get pods
kubectl get services
kubectl get ingress
```

## 🐛 트러블슈팅

### 일반적인 문제들

#### 1. AWS 권한 오류
```
Error: The security token included in the request is invalid
```
**해결방법**: AWS_ACCESS_KEY_ID와 AWS_SECRET_ACCESS_KEY를 다시 확인하세요.

#### 2. EKS 클러스터 접근 오류
```
Error: You must be logged in to the server (Unauthorized)
```
**해결방법**: EKS 클러스터의 aws-auth ConfigMap에 IAM 사용자를 추가하세요.

#### 3. ECR 권한 오류
```
Error: no basic auth credentials
```
**해결방법**: ECR 관련 IAM 권한을 확인하세요.

#### 4. 이미지 빌드 실패
**해결방법**: Dockerfile과 빌드 컨텍스트를 확인하세요.

### 로그 확인 방법

1. Actions 탭에서 실패한 워크플로우 클릭
2. 실패한 Job 클릭
3. 실패한 Step을 클릭하여 상세 로그 확인

## 🔄 롤백 방법

### 1. 이전 워크플로우 재실행
1. Actions 탭에서 성공한 이전 워크플로우 선택
2. "Re-run jobs" 클릭

### 2. 수동 롤백
```bash
# 특정 버전으로 롤백
kubectl set image deployment/auth-python auth-python=<ECR_URI>:<OLD_VERSION>
kubectl set image deployment/chat-node chat-node=<ECR_URI>:<OLD_VERSION>
kubectl set image deployment/ranking-java ranking-java=<ECR_URI>:<OLD_VERSION>
kubectl set image deployment/frontend frontend=<ECR_URI>:<OLD_VERSION>
```

## 📝 베스트 프랙티스

1. **브랜치 전략**: 단순한 main 브랜치 전략 사용
   - `main`: 모든 변경사항이 바로 배포됨
   - 필요시 feature 브랜치에서 작업 후 main으로 merge

2. **커밋 메시지**: Conventional Commits 사용 권장
   - `feat:` 새로운 기능
   - `fix:` 버그 수정
   - `docs:` 문서 수정
   - `style:` 코드 스타일 변경

3. **모니터링**: Datadog을 통한 실시간 모니터링 활용

4. **보안**: 정기적인 의존성 업데이트

## 🆘 지원

문제가 발생하거나 질문이 있는 경우:
1. 이 문서의 트러블슈팅 섹션 확인
2. GitHub Issues에 문제 보고
3. 워크플로우 로그 확인

---

**🎉 설정 완료 후 첫 배포를 위해 main 브랜치에 작은 변경사항을 푸시해보세요!**
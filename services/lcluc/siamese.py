"""Small shared-encoder U-Net for two-date binary change detection."""


def network(torch):
    nn = torch.nn
    fn = nn.functional

    def block(a, b):
        return nn.Sequential(nn.Conv2d(a, b, 3, padding=1), nn.ReLU(), nn.Conv2d(b, b, 3, padding=1), nn.ReLU())

    class SiameseUNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.enc1 = block(6, 8)
            self.enc2 = block(8, 16)
            self.middle = block(16, 32)
            self.dec2 = block(48, 16)
            self.dec1 = block(24, 8)
            self.head = nn.Conv2d(8, 2, 1)

        def encode(self, data):
            a = self.enc1(data)
            b = self.enc2(fn.max_pool2d(a, 2))
            return a, b, self.middle(fn.max_pool2d(b, 2))

        def forward(self, pair):
            a, b, c = (abs(first - last) for first, last in zip(self.encode(pair[:, :6]), self.encode(pair[:, 6:]), strict=True))
            up = fn.interpolate(c, size=b.shape[-2:], mode="bilinear", align_corners=False)
            d = self.dec2(torch.cat((up, b), dim=1))
            up = fn.interpolate(d, size=a.shape[-2:], mode="bilinear", align_corners=False)
            return self.head(self.dec1(torch.cat((up, a), dim=1)))

    return SiameseUNet()
